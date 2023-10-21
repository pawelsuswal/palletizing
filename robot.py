import logging
import time
from queue import Queue
from random import randint
from threading import Event


class Robot:
    def __init__(self, name, package_max_rows=4, package_max_cols=4):
        self.name: str = name

        self._package_max_rows = package_max_rows
        self._package_max_cols = package_max_cols

    def get_package(self) -> tuple:
        return randint(1, self._package_max_cols), randint(1, self._package_max_rows)


def robot_work(
        robot: Robot,
        started: Event,
        package_info_ready_to_read: Event,
        package_info_received: Event,
        place_position_ready_to_read: Event,
        place_position_received: Event,
        place_done: Event,
        place_done_confirmed: Event,
        package_data: Queue,
        place_position: Queue,
):
    from main import wait_for_signal
    logger = logging.getLogger(robot.name.capitalize())
    started.set()
    logger.info("Started")
    while True:
        package_data.put(robot.get_package())
        package_info_ready_to_read.set()
        logger.debug("Package info set, waiting for supervisor to read.")
        wait_for_signal(package_info_received, True, "package_info_received", "supervisor", logger)

        logger.debug("Supervisor had read package info.")
        package_info_ready_to_read.clear()
        wait_for_signal(package_info_received, False, "package_info_received", "supervisor", logger)

        logger.debug("Waiting for place position from supervisor.")
        wait_for_signal(place_position_ready_to_read, True, "place_position_ready_to_read", "supervisor", logger)
        place_position_data = place_position.get(block=False)
        logger.debug(f"Place position from supervisor received. Position received {place_position_data}")
        place_position_received.set()

        wait_for_signal(place_position_ready_to_read, False, "place_position_ready_to_read", "supervisor", logger)
        place_position_received.clear()

        place_done.set()
        logger.debug("Place done, waiting for confirmation.")
        wait_for_signal(place_done_confirmed, True, "place_done_confirmed", "supervisor", logger)

        place_done.clear()
        wait_for_signal(place_done_confirmed, False, "place_done_confirmed", "supervisor", logger)

        logger.debug("Task done, proceeding to next package.")

    logger.info("Finished")
