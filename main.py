import argparse
import logging
import time
from contextlib import suppress
from queue import Queue
from threading import Thread, Event

from exceptions import StopThread
from robot import Robot, robot_work
from pallet import Pallet
from settings import NEW_MESSAGE_SEPARATOR


def main(number_of_pallets: int, fast=False, step=False):
    # logging.basicConfig(level=logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    logger: logging.Logger = logging.getLogger("Main task")

    logger.info("Program starting")

    pallet: Pallet = Pallet(10, logger)
    pallet.print_layer()
    robot_1: Robot = Robot("robot 1")
    robot_2: Robot = Robot("robot 2")

    place_position: Queue = Queue(maxsize=1)
    end_thread: Event = Event()

    robot_1_thread: Thread = Thread(
        target=robot_work,
        args=[robot_1, place_position, end_thread, ],
        name="Robot 1 work"
    )
    robot_1_thread.start()

    robot_2_thread: Thread = Thread(
        target=robot_work,
        args=[robot_2, place_position, end_thread, ],
        name="Robot 2 work"
    )
    robot_2_thread.start()

    while not robot_1.started.is_set() or not robot_2.started.is_set():
        logger.warning(NEW_MESSAGE_SEPARATOR)
        logger.warning(f"Robots not reported to be ready to work. Robot 1 ready: {robot_1.started.is_set()}, "
                       f"robot 2 ready: {robot_2.started.is_set()}")
        time.sleep(1)

    logger.info("Robots are ready.")
    handle_robot_1 = True
    pallets_done: int = 0
    robot_to_handle = robot_1
    with suppress(KeyboardInterrupt):
        while not pallet.last_pallet or pallets_done < number_of_pallets:
            if pallets_done + 1 >= number_of_pallets:
                pallet.last_pallet = True

            logger.info(NEW_MESSAGE_SEPARATOR)
            msg_send = False

            while (not robot_1.package_info_ready_to_read.is_set() and handle_robot_1) or (
                    not robot_2.package_info_ready_to_read.is_set() and not handle_robot_1):
                if not msg_send:
                    logger.info(f"Waiting for package data from {robot_to_handle.name}.")
                    msg_send = True
                time.sleep(0.01)

            if step:
                input("\n" + "*" * 20 + "  Press any key to execute next task.  " + "*" * 20 + "\n")

            logger.info(f"Handling task from {robot_to_handle.name}")
            if handle_package_place(
                    pallet,
                    robot_to_handle,
                    place_position,
                    logger,
            ):
                pallets_done += 1

            if robot_to_handle == robot_1:
                robot_to_handle = robot_2
            else:
                robot_to_handle = robot_1

            if not fast:
                time.sleep(2)

    end_thread.set()

    robot_1_thread.join()
    robot_2_thread.join()


def handle_package_place(
        pallet: Pallet,
        robot: Robot,
        place_position: Queue,
        logger: logging.Logger,
) -> bool:
    """

    :param pallet: object representing current pallet state
    :param robot: robot that will place package on pallet
    :param place_position: queue object to pass information about place position to robot
    :param logger: Logger object to print messages
    :return: True when pallet was done else False
    """
    # read package info
    if pallet.current_layer_index > 0:
        pass
    package_info: tuple[int, int] = robot.package_data.get(block=False)
    robot.package_info_received.set()
    logger.info(f"Package info from {robot.name} received. Package size - rows: {package_info[1]}, "
                f"columns: {package_info[0]}")
    wait_for_signal(robot.package_info_ready_to_read, False, "package_info_ready_to_read", robot.name, logger)
    robot.package_info_received.clear()

    # find place position
    new_pallet: bool
    next_layer: bool
    calculated_place_position: tuple[int, int, int]
    new_pallet, next_layer, calculated_place_position = pallet.find_position(package_info)

    if new_pallet:
        pallet.update_pallet_layout(new_pallet, next_layer, calculated_place_position, package_info, logger)
        if pallet.last_pallet:
            return True

    place_position.put(calculated_place_position)
    robot.place_position_ready_to_read.set()
    wait_for_signal(robot.place_position_received, True, "package_info_received", robot.name, logger)

    robot.place_position_ready_to_read.clear()
    wait_for_signal(robot.place_position_received, False, "package_info_received", robot.name, logger)

    # placing package
    wait_for_signal(robot.place_done, True, "place_done", robot.name, logger)

    pallet_done: bool = pallet.update_pallet_layout(False, next_layer, calculated_place_position, package_info, logger)
    robot.place_done_confirmed.set()
    wait_for_signal(robot.place_done, False, "place_done", robot.name, logger)

    robot.place_done_confirmed.clear()
    # robot handling done, move to next task

    return pallet_done


def wait_for_signal(
        signal: Event,
        expected_state: bool,
        signal_name: str,
        thread_name: str,
        logger: logging.Logger,
        time_to_wait: float = 0.01,
        end_thread: Event | None = None,
):
    """
    
    :param signal: event to wait for 
    :param expected_state: state of event to wait for 
    :param signal_name: event name for displaying in debug message
    :param thread_name: thread name that should change event state
    :param logger: Logger used to display message in debug mode
    :param time_to_wait: time between next check of event state
    :param end_thread: event for break waiting, when end of thread was requested
    :return: 
    """
    message_printed: bool = False
    while (signal.is_set() and not expected_state) or (not signal.is_set() and expected_state):
        if expected_state:
            state: str = "set"
        else:
            state: str = "release"
        if not message_printed:
            logger.debug(f"Waiting for {thread_name} {state} {signal_name} signal")
            message_printed = True
        if end_thread is not None and end_thread.is_set():
            raise StopThread()
        time.sleep(time_to_wait)


if __name__ == "__main__":
    arg_parser: argparse.ArgumentParser = argparse.ArgumentParser()
    arg_parser.add_argument("--pallets", type=int, help="Provide number of pallets to do, default is 1")
    arg_parser.add_argument("-f", action="store_true", help="Fast mode - execute as fast as possible")
    arg_parser.add_argument(
        "-s",
        action="store_true",
        help="Step mode - before each task, user interaction is requested."
    )

    args = arg_parser.parse_args()

    number_of_pallets: int = args.pallets or 1

    main(number_of_pallets, fast=args.f, step=args.s)
