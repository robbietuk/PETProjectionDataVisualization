# Image orientation

How the viewer lays out each slice on screen. The tests pin it: `tests/model/test_orientation.py` (which
bins end up in which row and column) and `test_row_0_is_drawn_at_the_top_and_column_0_at_the_left` in
`tests/view/test_window_real_qt.py` (where rows and columns are drawn).

## The rule

A segment is read from STIR as an array of shape `(view, axial, tangential)`: the order of
`SegmentByView.as_array()`, checked against STIR's own `get_sinogram` and `get_viewgram` on real files by
`tests/stir_interface/test_real_stir_integration.py`. A slice keeps two of those axes in that order, with no
transpose and no flip:

- The **first** remaining axis runs **down** the screen (rows). Its smallest bin number is at the **top**.
- The **second** remaining axis runs **across** the screen (columns). Its smallest bin number is at the **left**.

This is the `matplotlib.pyplot.imshow` default (`origin="upper"`): row 0 at the top, column 0 at the left.

| Slice mode | Fixed index | Vertical axis (top → bottom) | Horizontal axis (left → right) |
| --- | --- | --- | --- |
| Sinogram | segment, axial position | view, min view → max view | tangential, most negative → most positive |
| Viewgram | segment, view | axial position, min → max of the segment | tangential, most negative → most positive |
| Tangential slice | segment, tangential position | view, min view → max view | axial position, min → max of the segment |

## Axis values

The axes show STIR's bin numbers, not array indices. An integer axis value is the **centre** of a pixel, so
the image covers `min - 0.5` to `max + 0.5` on each axis. For example, a sinogram with views 0..95 and
tangential positions -64..63 covers x from -64.5 to 63.5 and y from -0.5 (top) to 95.5 (bottom). The
axial numbers of a segment are those STIR gives for that segment (they need not start at 0). The value and
bin numbers under the cursor use the same mapping.

## Time of flight

TOF does not change the layout. *Bin* shows one TOF bin of the segment; *Sum*, *Mean* and *Max* reduce over
all TOF bins first. The slice is then taken from the result as in the table. TOF bin numbers are STIR's
(they are centred on 0 and may be negative). Non-TOF data has one bin.

## The old PyQt5 tool

The old viewer (`stir.projdata_visualisation`, in STIR's `examples/python`) draws STIR's sinograms and
viewgrams with matplotlib's `imshow`. If it passes `get_sinogram(...).as_array()` and
`get_viewgram(...).as_array()` without a transpose or `origin="lower"`, it follows the rule above. This has
**not yet been checked by eye** against the old tool on the same file; see issue #23.
