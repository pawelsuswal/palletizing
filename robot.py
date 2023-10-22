import logging
from contextlib import suppress
from queue import Queue
from random import randint
from threading import Event

from exceptions import StopThread
from settings import NEW_MESSAGE_SEPARATOR


class Robot:
    """
    Represents single robot instance with its own communication interface
    """
    def __init__(self, name, package_max_rows=4, package_max_cols=4):
        self.name: str = name

        self._package_max_rows = package_max_rows
        self._package_max_cols = package_max_cols

        self.started: Event = Event()
        self.package_info_ready_to_read: Event = Event()
        self.package_info_received: Event = Event()
        self.place_position_ready_to_read: Event = Event()
        self.place_position_received: Event = Event()
        self.place_done: Event = Event()
        self.place_done_confirmed: Event = Event()
        self.package_data: Queue = Queue(maxsize=1)

    def get_package(self) -> tuple[int, int]:
        """
        Generate random package data
        :return: Package size [columns, rows]
        """
        return randint(1, self._package_max_cols), randint(1, self._package_max_rows)


def robot_work(
        robot: Robot,
        place_position: Queue,
        end_thread: Event,
):
    """
    Executes robots work loop
    :param robot: Robot that will be controlled
    :param place_position: Queue object to read place position from
    :param end_thread: Event for ending thread
    :return:
    """
    from main import wait_for_signal
    logger = logging.getLogger(robot.name.capitalize())
    robot.started.set()
    logger.info(NEW_MESSAGE_SEPARATOR)
    logger.info("Started")

    with suppress(StopThread):
        while not end_thread.is_set():
            package_data: tuple[int, int] = robot.get_package()
            logger.info(NEW_MESSAGE_SEPARATOR)
            logger.info(f"Size of next package to handle - rows: {package_data[1]}, columns: {package_data[0]}")
            robot.package_data.put(package_data)
            robot.package_info_ready_to_read.set()
            wait_for_signal(
                robot.package_info_received,
                True,
                "package_info_received",
                "supervisor",
                logger,
                end_thread=end_thread
            )

            robot.package_info_ready_to_read.clear()
            wait_for_signal(
                robot.package_info_received,
                False,
                "package_info_received",
                "supervisor",
                logger,
                end_thread=end_thread
            )

            wait_for_signal(
                robot.place_position_ready_to_read,
                True,
                "place_position_ready_to_read",
                "supervisor",
                logger,
                end_thread=end_thread
            )
            place_position_data = place_position.get(block=False)
            robot.place_position_received.set()

            wait_for_signal(
                robot.place_position_ready_to_read,
                False,
                "place_position_ready_to_read",
                "supervisor",
                logger,
                end_thread=end_thread
            )
            robot.place_position_received.clear()

            robot.place_done.set()
            logger.info(NEW_MESSAGE_SEPARATOR)
            logger.info(f"Place done to - layer: {place_position_data[2]}, row: {place_position_data[1]}, "
                        f"column: {place_position_data[0]}")
            wait_for_signal(
                robot.place_done_confirmed,
                True,
                "place_done_confirmed",
                "supervisor",
                logger,
                end_thread=end_thread
            )

            robot.place_done.clear()
            wait_for_signal(
                robot.place_done_confirmed,
                False,
                "place_done_confirmed",
                "supervisor",
                logger,
                end_thread=end_thread
            )

    logger.info(NEW_MESSAGE_SEPARATOR)
    logger.info("Finished")
