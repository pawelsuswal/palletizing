import copy
import logging

from settings import NEW_MESSAGE_SEPARATOR


class Pallet:
    """
    Represents pallet
    """
    FREE_SPACE_CHAR = "0"
    OCCUPIED_SPACE_CHAR = "1"
    NEW_OBJECT_CHAR = "N"

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

        self._clear_pallet()
        self.last_pallet = False

    @property
    def current_layer_index(self):
        return self._current_layer_index

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

                place_position = (column_idx, row_idx, self._current_layer_index)
                break
            if place_position is not None:
                break

        if place_position is not None:
            return False, False, place_position

        if self._current_layer_index >= self._layers_to_do - 1:
            return True, False, (0, 0, 0)

        return False, True, (0, 0, self._current_layer_index + 1)

    def _clear_pallet(self):
        """
        Clear pallet data, used on object init and when new pallet have to be introduced
        :return:
        """
        self._current_layer_index = 0
        self._free_space_per_layer = [self._columns * self._rows] * self._layers_to_do
        for _ in range(self._layers_to_do):
            self._layers.append(copy.deepcopy(self._empty_layer))

    def update_pallet_layout(
            self,
            new_pallet: bool,
            next_layer: bool,
            place_position: tuple[int, int, int],
            package_size: tuple[int, int],
            logger: logging.Logger,
    ):
        """
        Updates current pallet state using provided package and place position data.
        :param new_pallet: if True current pallet will be reported and cleared
        :param next_layer: if True current layer index will be incremented, should not be used with new_pallet
        :param place_position: coordinates where package was ordered to be placed [column, row, layer]
        :param package_size: size of package placed on pallet [columns, rows]
        :param logger: Logger object used to display messages
        :return:
        """
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
                row[column_idx] = self.NEW_OBJECT_CHAR

        self.print_layer(show_with_previous=True)

        for row in current_layer[row_place_pos:row_upper_limit]:
            for column_idx in range(column_place_pos, column_upper_limit):
                row[column_idx] = self.OCCUPIED_SPACE_CHAR

        self._free_space_per_layer[self._current_layer_index] -= package_size_rows * package_size_columns

        if (self._current_layer_index == self._layers_to_do - 1
                and self._free_space_per_layer[self._current_layer_index] == 0):
            self._handle_new_pallet(logger)
            return True
        return False

    def _handle_new_pallet(self, logger: logging.Logger):
        """
        Display report about finished pallet and clear data as new pallet is introduced
        :param logger: Logger object used to display messages
        :return:
        """
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
        self._clear_pallet()

    def _check_space_for_package(
            self,
            layer: list[list[int]],
            col_check_limit: int,
            column_idx: int,
            row_check_limit: int,
            row_idx: int
    ):
        """
        Check if there is any occupied field in given coordinates in area of size of package
        :param layer: layer data
        :param col_check_limit: column index limit to check
        :param column_idx: column start index to check
        :param row_check_limit: row index limit to check
        :param row_idx: row start index to check
        :return: True if any field in area is occupied else False
        """
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
        """
        Prints current pallet layer
        :param show_empty: if True, prints empty layer template instead of current layer
        :param show_with_previous: if True, prints previous layer (if applicable) with current layer
        :return:
        """
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
