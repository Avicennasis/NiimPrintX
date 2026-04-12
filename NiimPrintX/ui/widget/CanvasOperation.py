from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

    from NiimPrintX.ui.config import CanvasState
    from NiimPrintX.ui.widget.ImageOperation import ImageOperation
    from NiimPrintX.ui.widget.TextOperation import TextOperation


class CanvasOperation:
    def __init__(self, canvas_state: CanvasState, text_op: TextOperation, img_op: ImageOperation) -> None:
        self.canvas_state: CanvasState = canvas_state
        self.text_op: TextOperation = text_op
        self.img_op: ImageOperation = img_op

    def canvas_click_handler(self, event: tk.Event[tk.Canvas]) -> None:
        """Deselect text/image if clicking outside the bounding box or on the resize handle."""
        clicked_on_text_handle = False
        clicked_on_image_handle = False

        # --- Text selection check ---
        if self.canvas_state.current_selected and self.canvas_state.current_selected in self.canvas_state.text_items:
            text_bbox = self.canvas_state.text_items[self.canvas_state.current_selected]["bbox"]
            text_bbox_handler = self.canvas_state.text_items[self.canvas_state.current_selected]["handle"]
            if text_bbox is not None and text_bbox_handler is not None:
                coords = self.canvas_state.canvas.coords(text_bbox)
                if len(coords) == 4:
                    x1, y1, x2, y2 = coords
                    h_coords = self.canvas_state.canvas.coords(text_bbox_handler)
                    if len(h_coords) == 4:
                        hx1, hy1, hx2, hy2 = h_coords

                        # Check if the click is on the handler
                        if hx1 <= event.x <= hx2 and hy1 <= event.y <= hy2:
                            clicked_on_text_handle = True

                        # Check if the click is inside the bounding box
                        elif not (x1 <= event.x <= x2 and y1 <= event.y <= y2):
                            self.text_op.deselect_text()

        # --- Image selection check ---
        if (
            self.canvas_state.current_selected_image
            and self.canvas_state.current_selected_image in self.canvas_state.image_items
        ):
            img_bbox = self.canvas_state.image_items[self.canvas_state.current_selected_image]["bbox"]
            img_bbox_handler = self.canvas_state.image_items[self.canvas_state.current_selected_image]["handle"]
            if img_bbox is not None and img_bbox_handler is not None:
                coords = self.canvas_state.canvas.coords(img_bbox)
                if len(coords) == 4:
                    x1, y1, x2, y2 = coords
                    h_coords = self.canvas_state.canvas.coords(img_bbox_handler)
                    if len(h_coords) == 4:
                        hx1, hy1, hx2, hy2 = h_coords

                        # Check if the click is on the handler
                        if hx1 <= event.x <= hx2 and hy1 <= event.y <= hy2:
                            clicked_on_image_handle = True

                        # Check if the click is inside the bounding box
                        elif not (x1 <= event.x <= x2 and y1 <= event.y <= y2):
                            self.img_op.deselect_image()

        # Clicking a text handle deselects any selected image, and vice versa
        if clicked_on_text_handle and self.canvas_state.current_selected_image:
            self.img_op.deselect_image()
        if clicked_on_image_handle and self.canvas_state.current_selected:
            self.text_op.deselect_text()
