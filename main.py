import argparse
import copy
import logging
import time
from queue import Queue
from threading import Thread, Event

from robot import Robot, robot_work

NEW_MESSAGE_SEPARATOR = "-" * 100


class Pallet:
    FREE_SPACE_CHAR = "0"
    OCCUPIED_SPACE_CHAR = "1"

    def __init__(self, layers_to_do: int, logger: logging.Logger, rows: int = 6, columns: int = 8):
        self._layers_to_do = layers_to_do
        self._rows = rows
        self._columns = columns
        self.logger = logger
        self._empty_row = []
        for _ in range(self._columns):
            self._empty_row.append(self.FREE_SPACE_CHAR)

        self._empty_layer = []
        for _ in range(self._rows):
            self._empty_layer.append(copy.copy(self._empty_row))

        self._current_layer_index = None
        self._free_space_per_layer = None
        self._layers = []

        self.clear_pallet()
        self.last_pallet = False

    def find_position(self, package_data: tuple[int, int]):
        """
        Looking for free area to place package on pallet.
        :param package_data: size of package in format [columns_size, rows_size]
        :return: tuple of 3 data:
            - bool: new pallet needed
            - bool: increase layer
            - tuple[int, int]: coordinates for placing package [col, row]
        """
        package_col_size, package_rows_size = package_data
        cols_limit = -(package_col_size - 1) if package_col_size > 1 else None
        row_limit = -(package_rows_size - 1) if package_rows_size > 1 else None
        place_position = None

        current_layer = self._layers[self._current_layer_index]
        if self._current_layer_index > 0:
            previous_layer = self._layers[self._current_layer_index - 1]
        else:
            previous_layer = None

        for row_idx, row in enumerate(current_layer[:row_limit]):
            for column_idx, column in enumerate(row[:cols_limit]):
                if column == self.OCCUPIED_SPACE_CHAR:
                    continue

                row_check_limit = row_idx + package_rows_size
                col_check_limit = column_idx + package_col_size

                if self._check_space_for_package(
                        current_layer,
                        col_check_limit,
                        column_idx,
                        row_check_limit,
                        row_idx):
                    continue

                if (previous_layer is not None
                        and not self._check_space_for_package(
                            previous_layer,
                            col_check_limit,
                            column_idx,
                            row_check_limit,
                            row_idx)):
                    continue

                place_position = (column_idx, row_idx)
                break
            if place_position is not None:
                break

        if place_position is not None:
            return False, False, place_position

        place_position = [0, 0]

        if self._current_layer_index >= self._layers_to_do - 1:
            return True, False, place_position

        return False, True, place_position

    def clear_pallet(self):
        self._current_layer_index = 0
        self._free_space_per_layer = [self._columns * self._rows] * self._layers_to_do
        for _ in range(self._layers_to_do):
            self._layers.append(copy.deepcopy(self._empty_layer))

    def update_pallet_layout(
            self,
            new_pallet: bool,
            next_layer: bool,
            place_position: tuple[int, int],
            package_size: tuple[int, int],
            logger: logging.Logger,
    ):
        if new_pallet:
            self._handle_new_pallet(logger)
            return True

        if next_layer:
            self._current_layer_index += 1

        current_layer = self._layers[self._current_layer_index]
        column_place_pos = place_position[0]
        row_place_pos = place_position[1]

        package_size_columns = package_size[0]
        package_size_rows = package_size[1]

        column_upper_limit = column_place_pos + package_size_columns
        row_upper_limit = row_place_pos + package_size_rows
        for row in current_layer[row_place_pos:row_upper_limit]:
            for column_idx in range(column_place_pos, column_upper_limit):
                row[column_idx] = self.OCCUPIED_SPACE_CHAR

        self.print_layer(show_with_previous=True)

        self._free_space_per_layer[self._current_layer_index] -= package_size_rows * package_size_columns

        if (self._current_layer_index == self._layers_to_do - 1
                and self._free_space_per_layer[self._current_layer_index] == 0):
            self._handle_new_pallet(logger)
            return True
        return False

    def _handle_new_pallet(self, logger):
        self.logger.info(NEW_MESSAGE_SEPARATOR)
        logger.warning("Pallet is full or there is not enough space for package.")
        logger.info("Current pallet statistics are:")
        logger.info("Layers were filled as below:")
        space_available = self._rows * self._columns
        total_space_available = space_available * self._layers_to_do
        total_space_left = 0
        for layer_idx, free_space in enumerate(self._free_space_per_layer, start=1):
            logger.info(f"Layer {layer_idx} have  {space_available - free_space} positions filled"
                        f"({round(free_space / space_available * 100, 2)}% of space left free).")
            total_space_left += free_space
        logger.info(f"\nPallet in total have {total_space_available - total_space_left} positions filled"
                    f"({round(total_space_left / total_space_available * 100, 2)}% of space left free).")
        if self.last_pallet:
            logger.info("Last pallet done.")
        else:
            logger.info("\nNew pallet is introduced.")
        self.clear_pallet()

    def _check_space_for_package(self, layer, col_check_limit, column_idx, row_check_limit, row_idx):
        occupied = False
        for local_row in layer[row_idx:row_check_limit]:
            for local_col in local_row[column_idx:col_check_limit]:
                if local_col == self.OCCUPIED_SPACE_CHAR:
                    occupied = True
                    break
            if occupied:
                break
        return occupied

    def print_layer(self, show_empty: bool = False, show_with_previous: bool = False):
        self.logger.info(NEW_MESSAGE_SEPARATOR)
        if show_empty:
            rows = [" ".join(row) for row in self._empty_layer]
            self.logger.info("Empty layer looks like that:")
            for row in rows:
                self.logger.info(row)
            return

        if show_with_previous and self._current_layer_index > 0:
            self.logger.info(f"Previous layer ({self._current_layer_index - 1})   |   "
                             f"Current layer ({self._current_layer_index}):")

            current_layer = self._layers[self._current_layer_index]
            previous_layer = self._layers[self._current_layer_index - 1]

            rows = [" ".join(row) for row in current_layer]
            prev_rows = [" ".join(row) for row in previous_layer]
            for idx in range(len(rows)):
                self.logger.info(f"{prev_rows[idx]}   |   {rows[idx]}")
        else:
            self.logger.info(f"Current layer ({self._current_layer_index}):")

            current_layer = self._layers[self._current_layer_index]

            rows = [" ".join(row) for row in current_layer]
            for idx in range(len(rows)):
                self.logger.info(f"{rows[idx]}")


def main(number_of_pallets: int):
    # logging.basicConfig(level=logging.DEBUG)
    logging.basicConfig(level=logging.INFO)
    logger: logging.Logger = logging.getLogger("Main task")

    logger.info("Program starting")

    pallet: Pallet = Pallet(10, logger)
    pallet.print_layer()
    robot_1: Robot = Robot("robot 1")
    robot_2: Robot = Robot("robot 2")

    place_position: Queue = Queue(maxsize=1)

    r1_package_data: Queue = Queue(maxsize=1)
    r1_started: Event = Event()
    r1_package_info_ready_to_read: Event = Event()
    r1_package_info_received: Event = Event()
    r1_place_position_ready_to_read: Event = Event()
    r1_place_position_received: Event = Event()
    r1_place_done: Event = Event()
    r1_place_done_confirmed: Event = Event()

    r2_package_data: Queue = Queue(maxsize=1)
    r2_started: Event = Event()
    r2_package_info_ready_to_read: Event = Event()
    r2_package_info_received: Event = Event()
    r2_place_position_ready_to_read: Event = Event()
    r2_place_position_received: Event = Event()
    r2_place_done: Event = Event()
    r2_place_done_confirmed: Event = Event()

    robot_1_thread: Thread = Thread(
        target=robot_work,
        args=[
            robot_1,
            r1_started,
            r1_package_info_ready_to_read,
            r1_package_info_received,
            r1_place_position_ready_to_read,
            r1_place_position_received,
            r1_place_done,
            r1_place_done_confirmed,
            r1_package_data,
            place_position,
        ],
        name="Robot 1 work"
    )
    robot_1_thread.start()

    robot_2_thread: Thread = Thread(
        target=robot_work,
        args=[
            robot_2,
            r2_started,
            r2_package_info_ready_to_read,
            r2_package_info_received,
            r2_place_position_ready_to_read,
            r2_place_position_received,
            r2_place_done,
            r2_place_done_confirmed,
            r2_package_data,
            place_position,
        ],
        name="Robot 2 work"
    )
    robot_2_thread.start()

    while not r1_started.is_set() or not r2_started.is_set():
        logger.warning(f"Robots not reported to be ready to work. Robot 1 ready: {r1_started.is_set()}, "
                       f"robot 2 ready: {r2_started.is_set()}")
        time.sleep(1)

    logger.info("Robots are ready.")
    handle_robot_1 = True
    pallets_done: int = 0
    while (not pallet.last_pallet or pallets_done < number_of_pallets):
        if pallets_done + 1 >= number_of_pallets:
            pallet.last_pallet = True
        logger.info(NEW_MESSAGE_SEPARATOR)
        while (not r1_package_info_ready_to_read.is_set() and handle_robot_1) or (
                not r2_package_info_ready_to_read.is_set() and not handle_robot_1):
            if handle_robot_1:
                robot_name = robot_1.name
            else:
                robot_name = robot_2.name
            logger.info(f"Waiting for package data from {robot_name}.")
            time.sleep(1)

        if handle_robot_1:
            logger.info("Handling task from robot 1")
            if handle_package_place(
                    pallet,
                    robot_1,
                    r1_package_info_ready_to_read,
                    r1_package_info_received,
                    r1_place_position_ready_to_read,
                    r1_place_position_received,
                    r1_place_done,
                    r1_place_done_confirmed,
                    place_position,
                    r1_package_data,
                    logger,
            ):
                pallets_done += 1
            handle_robot_1 = not handle_robot_1
        else:
            logger.info("Handling task from robot 2")
            if handle_package_place(
                    pallet,
                    robot_2,
                    r2_package_info_ready_to_read,
                    r2_package_info_received,
                    r2_place_position_ready_to_read,
                    r2_place_position_received,
                    r2_place_done,
                    r2_place_done_confirmed,
                    place_position,
                    r2_package_data,
                    logger,
            ):
                pallets_done += 1
            handle_robot_1 = not handle_robot_1
        time.sleep(1)

    robot_1_thread.join()
    robot_2_thread.join()


def handle_package_place(
        pallet: Pallet,
        robot: Robot,
        package_info_ready_to_read: Event,
        package_info_received: Event,
        place_position_ready_to_read: Event,
        place_position_received: Event,
        place_done: Event,
        place_done_confirmed: Event,
        place_position: Queue,
        package_data: Queue,
        logger: logging.Logger,
):
    # read package info
    if pallet._current_layer_index > 0:
        pass
    package_info = package_data.get(block=False)
    package_info_received.set()
    logger.info(f"Package info from {robot.name} received. Package: {package_info}")
    wait_for_signal(package_info_ready_to_read, False, "package_info_ready_to_read", robot.name, logger)
    package_info_received.clear()

    # find place position
    new_pallet, next_layer, calculated_place_position = pallet.find_position(package_info)
    if new_pallet:
        pallet.update_pallet_layout(new_pallet, next_layer, calculated_place_position, package_info, logger)
        if pallet.last_pallet:
            return True
    logger.debug(f"Place position for {robot.name} calculated.")

    place_position.put(calculated_place_position)
    place_position_ready_to_read.set()
    logger.debug(f"Place position allowed to read for {robot.name}.")
    wait_for_signal(place_position_received, True, "package_info_received", robot.name, logger)

    place_position_ready_to_read.clear()
    logger.debug(f"Place position not longer allowed to be read for {robot.name}.")
    wait_for_signal(place_position_received, False, "package_info_received", robot.name, logger)

    # placing package
    logger.debug(f"Waiting for {robot.name} to place package.")
    wait_for_signal(place_done, True, "place_done", robot.name, logger)

    logger.debug(f"{robot.name.capitalize()} reported finish placing.")
    pallet_done: bool = pallet.update_pallet_layout(False, next_layer, calculated_place_position, package_info, logger)
    place_done_confirmed.set()
    wait_for_signal(place_done, False, "place_done", robot.name, logger)

    place_done_confirmed.clear()
    # robot handling done, move to next task
    logger.debug(f"Finished handling task from {robot.name}, moving to next task.")

    return pallet_done


def wait_for_signal(
        signal: Event,
        expected_state: bool,
        signal_name: str,
        task_name: str,
        logger: logging.Logger,
        time_to_wait: float = 0.01
):
    message_printed = False
    while (signal.is_set() and not expected_state) or (not signal.is_set() and expected_state):
        if expected_state:
            state = "set"
        else:
            state = "release"
        if not message_printed:
            logger.debug(f"Waiting for {task_name} {state} {signal_name} signal")
            message_printed = True
        time.sleep(time_to_wait)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-p", type=int, help="Provide number of pallets to do, default is 1")

    args = arg_parser.parse_args()

    number_of_pallets = args.p or 1
    main(number_of_pallets)
