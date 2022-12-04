from ..plot import Plot
from ..layouts import GridPlot
from ..graphics import Image
from ipywidgets.widgets import IntSlider, VBox, HBox, Layout
import numpy as np
from typing import *
from warnings import warn
from functools import partial

DEFAULT_AXES_ORDER = \
    {
        2: "xy",
        3: "txy",
        4: "tzxy",
        # 5: "tczxy",  # no 5 dim stuff for now
    }


def calc_gridshape(n):
    sr = np.sqrt(n)
    return (
        int(np.ceil(sr)),
        int(np.round(sr))
    )


def is_arraylike(obj) -> bool:
    """
    Checks if the object is array-like.
    For now just checks if obj has `__getitem__()`
    """
    return hasattr(obj, "__getitem__")


class ImageWidget:
    """
    A high level for displaying n-dimensional image data in conjunction with automatically generated sliders for
    navigating through 1-2 selected dimensions within the image data.

    Can display a single n-dimensional image array or a grid of n-dimensional images.
    """
    def __init__(
            self,
            data: np.ndarray,
            axes_order: Union[str, Dict[np.ndarray, str]] = None,
            slider_axes: Union[str, int, List[Union[str, int]]] = None,
            slice_avg: Dict[Union[int, str], int] = None,
            frame_apply: Union[callable, Dict[Union[int, str], callable]] = None,
            grid_shape: Tuple[int, int] = None,
            **kwargs
    ):
        if isinstance(data, list):
            # verify that it's a list of np.ndarray
            if all([is_arraylike(d) for d in data]):
                if grid_shape is None:
                    grid_shape = calc_gridshape(len(data))

                # verify that user-specified grid shape is large enough for the number of image arrays passed
                elif grid_shape[0] * grid_shape[1] < len(data):
                    grid_shape = calc_gridshape(len(data))
                    warn(f"Invalid `grid_shape` passed, setting grid shape to: {grid_shape}")

                _ndim = [d.ndim for d in data]

                # verify that all image arrays have same number of dimensions
                # sliders get messy otherwise
                if not len(set(_ndim)) == 1:
                    raise ValueError(
                        f"Number of dimensions of all data arrays must match, your ndims are: {_ndim}"
                    )

                self.data: List[np.ndarray] = data
                self.ndim = self.data[0].ndim  # all ndim must be same

                self.plot_type = "grid"

            else:
                raise TypeError(
                    f"`data` must be a  list of `numpy.ndarray` representing a grid of images/image sequences"
                )

        elif is_arraylike(data):
            self.data = [data]
            self.ndim = self.data[0].ndim

            self.plot_type = "single"
        else:
            raise TypeError(
                f"`data` must be of type `numpy.ndarray` representing a single image/image sequence "
                f"or a  list of `numpy.ndarray` representing a grid of images/image sequences"
            )

        # default axes order if not passed
        if axes_order is None:
            self.axes_order: List[str] = [DEFAULT_AXES_ORDER[self.ndim]] * len(self.data)

        elif isinstance(axes_order, str):
            self.axes_order: List[str] = [axes_order] * len(self.data)
        elif isinstance(axes_order, dict):
            self.axes_order: List[str] = [DEFAULT_AXES_ORDER[self.ndim]] * len(self.data)

            # dict of {array: axis_order_str}
            for array in list(axes_order.keys()):
                # get index of corresponding array in data list
                try:
                    data_ix = None
                    for i in range(len(self.data)):
                        if self.data[i] is array:
                            data_ix = i
                            break
                    if data_ix is None:
                        raise ValueError(
                            f"Given `array` not found in `self.data`"
                        )
                except Exception:
                    raise TypeError(
                        f"`axes_order` must be a <str> or <Dict[array: str]>, "
                        f"with the same array object(s) passed to `data`"
                    )
                # set corresponding axes order from passed `axes_order` dict
                if not set(axes_order[array]) == set(DEFAULT_AXES_ORDER[self.ndim]):
                    raise ValueError(
                        f"Invalid axis order passed for one of your arrays, "
                        f"valid axis order for given number of dimensions "
                        f"can only contain the following characters: "
                        f"{DEFAULT_AXES_ORDER[self.ndim]}"
                    )
                self.axes_order[data_ix] = axes_order[array]
        else:
            raise TypeError(f"`axes_order` must be a <str> or <Dict[array: str]>, you have passed a: <{type(axes_order)}>")

        if not len(self.axes_order[0]) == self.ndim:
            raise ValueError(
                f"Number of axes specified by `axes_order`: {len(self.axes_order[0])} does not"
                f" match number of dimensions in the `data`: {self.ndim}"
            )

        ao = np.array([sorted(v) for v in self.axes_order])

        if not np.all(ao == ao[0]):
            raise ValueError(
                f"`axes_order` for all arrays must contain the same combination of dimensions, your `axes_order` are: "
                f"{self.axes_order}"
            )

        # by default slider is only made for "t" - time dimension
        if slider_axes is None:
            slider_axes = "t"

        # slider for only one of the dimensions
        if isinstance(slider_axes, (int, str)):
            # if numerical dimension is specified
            if isinstance(slider_axes, int):
                ao = np.array([v for v in self.axes_order])
                if not np.all(ao == ao[0]):
                    raise ValueError(
                        f"`axes_order` for all arrays must be identical if passing in a <int> `slider_axes` argument. "
                        f"Pass in a <str> argument if the `axes_order` are different for each array."
                    )
                self.slider_axes: List[str] = [self.axes_order[0][slider_axes]]

            # if dimension specified by str
            elif isinstance(slider_axes, str):
                if slider_axes not in self.axes_order[0]:
                    raise ValueError(
                        f"if `slider_axes` is a <str>, it must be a character found in `axes_order`. "
                        f"Your `axes_order` characters are: {set(self.axes_order[0])}."
                    )
                self.slider_axes: List[str] = [slider_axes]

        # multiple sliders, one for each dimension
        elif isinstance(slider_axes, list):
            self.slider_axes: List[str] = list()

            for sax in slider_axes:
                if isinstance(sax, int):
                    ao = np.array([v for v in self.axes_order])
                    if not np.all(ao == ao[0]):
                        raise ValueError(
                            f"`axes_order` for all arrays must be identical if passing in a <int> `slider_axes` argument. "
                            f"Pass in a <str> argument if the `axes_order` are different for each array."
                        )
                    # parse int to a str
                    self.slider_axes.append(self.axes_order[0][sax])

                elif isinstance(sax, str):
                    if sax not in self.axes_order[0]:
                        raise ValueError(
                            f"if `slider_axes` is a <str>, it must be a character found in `axes_order`. "
                            f"Your `axes_order` characters are: {set(self.axes_order[0])}."
                        )
                    self.slider_axes.append(sax)

                else:
                    raise TypeError(
                        "If passing a list for `slider_axes` each element must be either an <int> or <str>"
                    )

        else:
            raise TypeError(f"`slider_axes` must a <int>, <str> or <list>, you have passed a: {type(slider_axes)}")

        self.sliders = list()
        self.vertical_sliders = list()
        self.horizontal_sliders = list()

        # current_index stores {dimension_index: slice_index} for every dimension
        self.current_index: Dict[str, int] = {sax: 0 for sax in self.slider_axes}

        if self.plot_type == "single":
            self.plot: Plot = Plot()
            frame = self.get_2d_slice(self.data[0], slice_indices=self.current_index)

            self.image_graphics: List[Image] = [self.plot.image(data=frame, **kwargs)]

        elif self.plot_type == "grid":
            self.plot: GridPlot = GridPlot(shape=grid_shape, controllers="sync")

            self.image_graphics = list()
            for d, subplot in zip(self.data, self.plot):
                frame = self.get_2d_slice(d, slice_indices=self.current_index)
                ig = Image(frame, **kwargs)
                subplot.add_graphic(ig)
                self.image_graphics.append(ig)

        self.plot.renderer.add_event_handler(self.set_slider_layout, "resize")

        # get max bound for all sliders using the max index for that dim from all arrays
        slider_axes_max = {k: np.inf for k in self.slider_axes}
        for axis in list(slider_axes_max.keys()):
            for array, order in zip(self.data, self.axes_order):
                slider_axes_max[axis] = min(slider_axes_max[axis], array.shape[order.index(axis)])

        for sax in self.slider_axes:
            if sax == "z":
                # TODO: once ipywidgets plays nicely with HBox and jupyter-rfb can use vertical
                # orientation = "vertical"
                orientation = "horizontal"
            else:
                orientation = "horizontal"

            slider = IntSlider(
                min=0,
                max=slider_axes_max[sax] - 1,
                step=1,
                value=0,
                description=f"Axis: {sax}",
                orientation=orientation
            )

            slider.observe(
                partial(self.slider_value_changed, sax),
                names="value"
            )

            self.sliders.append(slider)
            if orientation == "horizontal":
                self.horizontal_sliders.append(slider)
            elif orientation == "vertical":
                self.vertical_sliders.append(slider)

        # TODO: So just stack everything vertically for now
        self.widget = VBox([
            self.plot.canvas,
            *self.sliders
        ])

        # TODO: there is currently an issue with ipywidgets or jupyter-rfb and HBox doesn't work with RFB canvas
        # self.widget = None
        # hbox = None
        # if len(self.vertical_sliders) > 0:
        #     hbox = HBox(self.vertical_sliders)
        #
        # if len(self.horizontal_sliders) > 0:
        #     if hbox is not None:
        #         self.widget = VBox([
        #             HBox([self.plot.canvas, hbox]),
        #             *self.horizontal_sliders,
        #         ])
        #
        #     else:
        #         self.widget = VBox([self.plot.canvas, *self.horizontal_sliders])

    def get_2d_slice(
            self,
            array: np.ndarray,
            slice_indices: dict[Union[int, str], int]
    ) -> np.ndarray:
        """
        Get the 2D array from the given slice indices.

        Parameters
        ----------
        array: np.ndarray
            array-like to get a 2D slice from

        slice_indices: dict[int, int]
            dict in form of {dimension_index: slice_index}
            For example if an array has shape [1000, 30, 512, 512] corresponding to [t, z, x, y]:
                To get the 100th timepoint and 3rd z-plane pass:
                    {"t": 100, "z": 3}, or {0: 100, 1: 3}

        Returns
        -------
        np.ndarray
            array-like, 2D slice

        Examples
        --------
        img = get_2d_slice(a, {"t": 50, "z": 4})
        # img is a 2d plane at time index 50 and z-plane 4

        """
        indexer = [slice(None)] * self.ndim

        for dim in list(slice_indices.keys()):
            if isinstance(dim, str):
                data_ix = None
                for i in range(len(self.data)):
                    if self.data[i] is array:
                        data_ix = i
                        break
                if data_ix is None:
                    raise ValueError(
                        f"Given `array` not found in `self.data`"
                    )
                # get axes order for that specific array
                numerical_dim = self.axes_order[data_ix].index(dim)
            else:
                numerical_dim = dim

            indexer[numerical_dim] = slice_indices[dim]

        return array[tuple(indexer)]

    def slider_value_changed(
            self,
            dimension: int,
            change: dict
    ):
        self.current_index[dimension] = change["new"]

        for ig, data in zip(self.image_graphics, self.data):
            frame = self.get_2d_slice(data, self.current_index)
            ig.update_data(frame)

    def set_slider_layout(self, *args):
        w, h = self.plot.renderer.logical_size
        for hs in self.horizontal_sliders:
            hs.layout = Layout(width=f"{w}px")

        for vs in self.vertical_sliders:
            vs.layout = Layout(height=f"{h}px")

    def show(self):
        # start render loop
        self.plot.show()

        return self.widget
