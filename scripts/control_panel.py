from __future__ import annotations

import threading


_STARTED = set()
_LOCK = threading.Lock()


def _start_once(key, target):
    with _LOCK:
        if key in _STARTED:
            return
        _STARTED.add(key)
    threading.Thread(target=target, daemon=True).start()


def _place_bottom_right(root):
    root.update_idletasks()
    margin = 24
    pos_x = max(0, root.winfo_screenwidth() - root.winfo_width() - margin)
    pos_y = max(0, root.winfo_screenheight() - root.winfo_height() - margin)
    root.geometry(f"+{pos_x}+{pos_y}")


def _setup_root(title, geometry):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(title)
    root.geometry(geometry)
    root.resizable(True, True)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    root.option_add("*Font", ("DejaVu Sans", 15))
    style = ttk.Style(root)
    style.configure("TLabel", font=("DejaVu Sans", 15))
    style.configure("TButton", font=("DejaVu Sans", 15))
    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return root, frame, ttk, tk


def start_force_control_panel_once(control_state, config, recording_state=None):
    def gui_thread():
        try:
            root, frame, ttk, tk = _setup_root("Endovascular Force Control", "700x230")
        except Exception as exc:
            print(f"[Endovascular GUI] tkinter unavailable: {exc}")
            return

        force_intensity = control_state.get_roi_force()
        force_var = tk.DoubleVar(value=force_intensity)
        force_value = ttk.Label(frame, text=f"{force_intensity:.3f} N")

        def on_force_change(value):
            control_state.set_roi_force(intensity=float(value))
            force_value.config(text=f"{float(value):.3f} N")

        ttk.Label(frame, text="ROI Force Intensity").grid(row=0, column=0, sticky="w")
        force_scale = ttk.Scale(
            frame,
            from_=0.0,
            to=config.aorta.max_force_intensity,
            orient="horizontal",
            variable=force_var,
            command=on_force_change,
            length=500,
        )
        force_scale.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        force_value.grid(row=1, column=1, sticky="e")

        record_text = tk.StringVar(value="Record Displacement")

        def toggle_recording():
            if recording_state is None:
                return
            requested = not bool(recording_state.get("displacement_requested", False))
            recording_state["displacement_requested"] = requested
            record_text.set("Stop Recording" if requested else "Record Displacement")

        ttk.Button(frame, textvariable=record_text, command=toggle_recording).grid(row=2, column=0, sticky="w", pady=(18, 0))

        root.after(0, lambda: _place_bottom_right(root))
        root.mainloop()

    _start_once("force", gui_thread)


def start_catheter_control_panel_once(control_state, config, recording_state=None):
    def gui_thread():
        try:
            root, frame, ttk, tk = _setup_root("Endovascular Catheter Control", "780x390")
        except Exception as exc:
            print(f"[Endovascular GUI] tkinter unavailable: {exc}")
            return

        insertion, rotation_deg = control_state.get_catheter()
        speed_mm_s = control_state.get_catheter_speed() * 1000.0
        speed_var = tk.DoubleVar(value=speed_mm_s)
        rotation_var = tk.DoubleVar(value=rotation_deg)
        speed_value = ttk.Label(frame, text=f"{speed_mm_s:.1f} mm/s")
        insertion_value = ttk.Label(frame, text=f"Inserted: {insertion * 1000.0:.1f} mm")
        rotation_value = ttk.Label(frame, text=f"{rotation_deg:.1f} deg")
        catheter_auto_text = tk.StringVar(value="Start Insertion")
        record_text = tk.StringVar(value="Record Insertion")

        def on_speed_change(value):
            speed_m_s = control_state.set_catheter_speed(float(value) / 1000.0)
            speed_value.config(text=f"{speed_m_s * 1000.0:.1f} mm/s")

        def on_rotation_change(value):
            control_state.set_catheter(rotation_deg=float(value))
            rotation_value.config(text=f"{float(value):.1f} deg")

        ttk.Label(frame, text="Catheter Insertion Speed").grid(row=0, column=0, sticky="w")
        speed_scale = ttk.Scale(
            frame,
            from_=1.0,
            to=35.0,
            orient="horizontal",
            variable=speed_var,
            command=on_speed_change,
            length=560,
        )
        speed_scale.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        speed_value.grid(row=1, column=1, sticky="e")
        insertion_value.grid(row=2, column=0, sticky="w", pady=(8, 0))

        ttk.Label(frame, text="Catheter Rotation").grid(row=3, column=0, sticky="w", pady=(12, 0))
        rotation_scale = ttk.Scale(
            frame,
            from_=config.catheter.min_rotation_deg,
            to=config.catheter.max_rotation_deg,
            orient="horizontal",
            variable=rotation_var,
            command=on_rotation_change,
            length=560,
        )
        rotation_scale.grid(row=4, column=0, sticky="ew", padx=(0, 10))
        rotation_value.grid(row=4, column=1, sticky="e")

        def reset_catheter():
            next_insertion, next_rotation = control_state.reset_catheter()
            rotation_var.set(next_rotation)
            insertion_value.config(text=f"Inserted: {next_insertion * 1000.0:.1f} mm")
            rotation_value.config(text=f"{next_rotation:.1f} deg")

        def toggle_catheter_auto():
            running = control_state.toggle_catheter_auto()
            catheter_auto_text.set("Stop Insertion" if running else "Start Insertion")

        def toggle_recording():
            if recording_state is None:
                return
            requested = not bool(recording_state.get("insertion_requested", False))
            recording_state["insertion_requested"] = requested
            record_text.set("Stop Recording" if requested else "Record Insertion")

        def sync_catheter_controls():
            next_insertion, next_rotation = control_state.get_catheter()
            rotation_var.set(next_rotation)
            next_speed_mm_s = control_state.get_catheter_speed() * 1000.0
            speed_var.set(next_speed_mm_s)
            speed_value.config(text=f"{next_speed_mm_s:.1f} mm/s")
            insertion_value.config(text=f"Inserted: {next_insertion * 1000.0:.1f} mm")
            rotation_value.config(text=f"{next_rotation:.1f} deg")
            catheter_auto_text.set("Stop Insertion" if control_state.catheter_auto_running() else "Start Insertion")
            root.after(100, sync_catheter_controls)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=2, sticky="w", pady=(22, 0))
        ttk.Button(button_frame, textvariable=catheter_auto_text, command=toggle_catheter_auto).grid(row=0, column=0)
        ttk.Button(button_frame, text="Catheter Reset", command=reset_catheter).grid(row=0, column=1, padx=(12, 0))
        ttk.Button(button_frame, textvariable=record_text, command=toggle_recording).grid(row=0, column=2, padx=(12, 0))

        root.after(0, lambda: _place_bottom_right(root))
        root.after(100, sync_catheter_controls)
        root.mainloop()

    _start_once("catheter", gui_thread)
