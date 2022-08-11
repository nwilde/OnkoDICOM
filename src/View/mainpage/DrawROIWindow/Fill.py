import math

import numpy
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsEllipseItem

import src.constants as constant
from src.constants import DEFAULT_WINDOW_SIZE
from src.Model.Transform import linear_transform, get_pixel_coords, \
    get_first_entry, inv_linear_transform


# noinspection PyAttributeOutsideInit

class Fill(QtWidgets.QGraphicsScene):
    """
        Class responsible for the ROI drawing functionality
        """

    # Initialisation function  of the class
    def __init__(self, imagetoPaint, pixmapdata, min_pixel, max_pixel, dataset,
                 draw_roi_window_instance, slice_changed,
                 current_slice, drawing_tool_radius, keep_empty_pixel,
                 target_pixel_coords=set()):
        super(Fill, self).__init__()

        # create the canvas to draw the line on and all its necessary
        # components
        self.dataset = dataset
        self.rows = dataset['Rows'].value
        self.cols = dataset['Columns'].value
        self.draw_roi_window_instance = draw_roi_window_instance
        self.slice_changed = slice_changed
        self.current_slice = current_slice
        self.min_pixel = min_pixel
        self.max_pixel = max_pixel
        self.addItem(QGraphicsPixmapItem(imagetoPaint))
        self.img = imagetoPaint
        self.data = pixmapdata
        self.values = []
        self.getValues()
        self.rect = QtCore.QRect(250, 300, 20, 20)
        self.update()
        self._points = {}
        self._circlePoints = []
        self.drag_position = QtCore.QPoint()
        self.cursor = None
        self.polygon_preview = []
        self.isPressed = False
        self.pixel_array = None
        self.pen = QtGui.QPen(QtGui.QColor("yellow"))
        self.pen.setStyle(QtCore.Qt.DashDotDotLine)
        # This will contain the new pixel coordinates specified by the min
        # and max pixel density
        self.target_pixel_coords = target_pixel_coords
        self.according_color_dict = {}
        self.q_image = None
        self.q_pixmaps = None
        self.label = QtWidgets.QLabel()
        self.draw_tool_radius = drawing_tool_radius
        self.is_current_pixel_coloured = False
        self.keep_empty_pixel = keep_empty_pixel

    def _display_pixel_color(self, x, y):
        """
        Creates the initial list of pixel values within the given minimum
        and maximum densities, then displays them on the view.
        """
        color = QtGui.QColor()
        color.setRgb(90, 250, 175, 200)
        # self.target_pixel_coords.add((x, y))
        self.q_image = self.img.toImage()
        # self.q_image.setPixelColor(x, y, color)

        # TODO Remove for loop was to test saving
        #  need to have multiple points to save if only single point it won't save
        for xx in range(200, 221):
            for yy in range(200, 221):
                self.q_image.setPixelColor(xx, yy, color)
                self.target_pixel_coords.add((xx, yy))

        self.refresh_image()

    def refresh_image(self):
        """
        Convert QImage containing modified CT slice with highlighted pixels
        into a QPixmap, and then display it onto the view.
        """
        self.q_pixmaps = QtWidgets.QGraphicsPixmapItem(
            QtGui.QPixmap.fromImage(self.q_image))
        self.addItem(self.q_pixmaps)

    def getValues(self):
        """
        This function gets the corresponding values of all the points in the
        drawn line from the dataset.
        """
        for i in range(DEFAULT_WINDOW_SIZE):
            for j in range(DEFAULT_WINDOW_SIZE):
                x, y = linear_transform(
                    i, j, self.rows, self.cols)
                self.values.append(self.data[x][y])

    def mousePressEvent(self, event):
        """
            This method is called to handle a mouse press event
            :param event: the mouse event
        """
        x = event.scenePos().x()
        y = event.scenePos().y()
        print(event.scenePos().x())
        print(event.scenePos().y())
        self._display_pixel_color(x, y)

        self.update()

# TODO add saving functionality
# AND
# TODO add filling algorithm