from PIL import Image, ImageTk


class ImageOperation:
    def __init__(self, config):
        self.config = config

    def load_image(self, file_path):
        try:
            raw_image = Image.open(file_path)
            source_image = raw_image.convert("RGBA")
            raw_image.close()
        except Exception as e:
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Failed to load image: {e}")
            return

        x1, y1, x2, y2 = self.config.canvas.bbox(self.config.bounding_box)
        canvas_width = x2 - x1
        canvas_height = y2 - y1

        img_width, img_height = source_image.size
        scale_factor = min(canvas_width / img_width, canvas_height / img_height)
        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)
        resized_image = source_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(resized_image)

        image_id = self.config.canvas.create_image(0, 0, image=img_tk, anchor="nw")
        self.config.image_items[image_id] = {
            "image": img_tk,
            "original_image": source_image,  # Full-res, not resized
            "bbox": None,
            "handle": None
        }

        # Make the image draggable and resizable
        self.config.canvas.tag_bind(image_id, "<Button-1>",
                                    lambda event, img_id=image_id: self.select_image(event, img_id))
        self.config.canvas.tag_bind(image_id, "<Button1-Motion>", lambda e, img_id=image_id: self.move_image(e, img_id))

    def start_image_resize(self, event, image_id):
        self.config.image_items[image_id]['initial_y'] = event.y
        self.config.image_items[image_id]['initial_x'] = event.x

    def select_image(self, event, image_id):
        """Select and draw a bounding box around the image."""
        self.deselect_image()
        self.config.current_selected_image = image_id
        # Draw a bounding box
        bb = self.config.canvas.bbox(image_id)
        bbox = self.config.canvas.create_rectangle(bb, outline="blue", width=2)
        handle = self.config.canvas.create_oval(
            bb[2] - 5,
            bb[3] - 5,
            bb[2] + 5,
            bb[3] + 5,
            outline="blue",
            fill="gray"
        )

        self.config.image_items[image_id].update({
            "bbox": bbox,
            "handle": handle,
            "initial_x": event.x,
            "initial_y": event.y
        })
        self.config.canvas.tag_bind(
            handle, "<Button1-Motion>", lambda e, img_id=image_id: self.resize_image(e, img_id)
        )
        self.config.canvas.tag_bind(handle, "<Button-1>", lambda e: self.start_image_resize(e, image_id))

    def deselect_image(self):
        """Deselect the current image."""
        if self.config.current_selected_image:
            if "bbox" in self.config.image_items[self.config.current_selected_image]:
                self.config.canvas.delete(self.config.image_items[self.config.current_selected_image]["bbox"])
                self.config.canvas.delete(self.config.image_items[self.config.current_selected_image]["handle"])
            self.config.current_selected_image = None

    def move_image(self, event, image_id):
        """Move the selected image."""
        if self.config.image_items[image_id].get("bbox") is None:
            return
        dx = event.x - self.config.image_items[image_id]["initial_x"]
        dy = event.y - self.config.image_items[image_id]["initial_y"]
        self.config.canvas.move(image_id, dx, dy)
        self.config.canvas.move(self.config.image_items[image_id]["bbox"], dx, dy)
        self.config.canvas.move(self.config.image_items[image_id]["handle"], dx, dy)
        self.config.image_items[image_id]["initial_x"] = event.x
        self.config.image_items[image_id]["initial_y"] = event.y

    def resize_image(self, event, image_id):
        """Resize the selected image based on the mouse event."""
        # Get the initial bounding box
        current_bbox = self.config.canvas.bbox(image_id)
        initial_width = current_bbox[2] - current_bbox[0]
        current_bbox[3] - current_bbox[1]

        # Calculate the movement since the last event
        dx = event.x - self.config.image_items[image_id]["initial_x"]
        event.y - self.config.image_items[image_id]["initial_y"]

        # Always resize from the original image to maintain quality
        original_image = self.config.image_items[image_id]["original_image"]

        # Calculate the new size based on the mouse movement, preserving aspect ratio
        orig_w, orig_h = original_image.size
        aspect = orig_w / orig_h
        new_width = max(initial_width + dx, 20)  # Ensure a minimum width
        new_height = max(int(new_width / aspect), 20)  # Lock aspect ratio

        # Resize the image to the new size
        resized_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(resized_image)

        # Update the canvas with the resized image
        self.config.canvas.itemconfig(image_id, image=img_tk)
        self.config.image_items[image_id]["image"] = img_tk

        # Update the bounding box and handle
        self.update_image_bbox_and_handle(image_id)

        # Update the initial coordinates for the next resizing operation
        self.config.image_items[image_id]["initial_x"] = event.x
        self.config.image_items[image_id]["initial_y"] = event.y

    def update_image_bbox_and_handle(self, image_id):
        """Update bounding box and handle for the image."""
        bbox_coords = self.config.canvas.bbox(image_id)
        self.config.canvas.coords(self.config.image_items[image_id]["bbox"], bbox_coords)
        self.config.canvas.coords(
            self.config.image_items[image_id]["handle"],
            bbox_coords[2] - 5,
            bbox_coords[3] - 5,
            bbox_coords[2] + 5,
            bbox_coords[3] + 5,
        )

    def delete_image(self):
        if self.config.current_selected_image:
            item = self.config.image_items[self.config.current_selected_image]
            self.config.canvas.delete(self.config.current_selected_image)
            if item.get("bbox"):
                self.config.canvas.delete(item["bbox"])
            if item.get("handle"):
                self.config.canvas.delete(item["handle"])
            del self.config.image_items[self.config.current_selected_image]
            self.config.current_selected_image = None
