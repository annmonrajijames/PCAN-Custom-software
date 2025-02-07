import tkinter as tk
from tkinter import ttk, messagebox
import can

def create_parameter_window():
    param_win = tk.Toplevel(root)
    param_win.title("Create Parameter")

    # --- Parameter Details ---
    tk.Label(param_win, text="Parameter Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    param_name_entry = tk.Entry(param_win)
    param_name_entry.grid(row=0, column=1, padx=5, pady=2)

    tk.Label(param_win, text="CAN ID (hex):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    can_id_entry = tk.Entry(param_win)
    can_id_entry.grid(row=1, column=1, padx=5, pady=2)

    tk.Label(param_win, text="Parameter Size:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    size_options = [
        "1 bit", "2 bit", "3 bit", "4 bit", "5 bit", "6 bit", "7 bit", "8 bit",
        "2 byte", "3 byte", "4 byte", "5 byte", "6 byte", "7 byte", "8 byte"
    ]
    size_var = tk.StringVar(value=size_options[0])
    size_menu = ttk.Combobox(param_win, textvariable=size_var, values=size_options, state="readonly", width=10)
    size_menu.grid(row=2, column=1, padx=5, pady=2)

    tk.Label(param_win, text="Parameter Type:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
    type_options = ["Unsigned", "Signed"]
    type_var = tk.StringVar(value=type_options[0])
    type_menu = ttk.Combobox(param_win, textvariable=type_var, values=type_options, state="readonly", width=10)
    type_menu.grid(row=3, column=1, padx=5, pady=2)

    tk.Label(param_win, text="Resolution:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
    resolution_entry = tk.Entry(param_win)
    resolution_entry.insert(0, "1")
    resolution_entry.grid(row=4, column=1, padx=5, pady=2)

    # --- Mapping Options ---
    mapping_frame = tk.Frame(param_win)
    mapping_frame.grid(row=5, column=0, columnspan=3, pady=10)

    def update_mapping_options(*args):
        for widget in mapping_frame.winfo_children():
            widget.destroy()
        size_str = size_var.get()
        mapping_vars = []
        if "bit" in size_str:
            num_bits = int(size_str.split()[0])
            tk.Label(mapping_frame, text="Select Bit Positions (order):").grid(row=0, column=0, columnspan=num_bits)
            for i in range(num_bits):
                var = tk.StringVar(value="0")
                mapping_vars.append(var)
                bit_menu = ttk.Combobox(mapping_frame, textvariable=var, values=[str(x) for x in range(8)], state="readonly", width=3)
                bit_menu.grid(row=1, column=i, padx=2)
        else:
            num_bytes = int(size_str.split()[0])
            tk.Label(mapping_frame, text="Select Byte Positions (order):").grid(row=0, column=0, columnspan=num_bytes)
            for i in range(num_bytes):
                var = tk.StringVar(value="0")
                mapping_vars.append(var)
                byte_menu = ttk.Combobox(mapping_frame, textvariable=var, values=[str(x) for x in range(8)], state="readonly", width=3)
                byte_menu.grid(row=1, column=i, padx=2)
        mapping_frame.mapping_vars = mapping_vars

    size_var.trace("w", update_mapping_options)
    update_mapping_options()

    # --- Parameter Value (Slider and Entry) ---
    tk.Label(param_win, text="Parameter Value:").grid(row=6, column=0, sticky="w", padx=5, pady=2)
    param_value_var = tk.IntVar(value=0)
    slider = tk.Scale(param_win, variable=param_value_var, from_=0, to=100, orient=tk.HORIZONTAL)
    slider.grid(row=6, column=1, padx=5, pady=2, sticky="we")
    entry = tk.Entry(param_win, textvariable=param_value_var, width=10)
    entry.grid(row=6, column=2, padx=5, pady=2)

    def update_slider_range(*args):
        size_str = size_var.get()
        if "bit" in size_str:
            num_bits = int(size_str.split()[0])
            if type_var.get() == "Unsigned":
                min_val, max_val = 0, (2 ** num_bits) - 1
            else:
                min_val, max_val = -(2 ** (num_bits - 1)), (2 ** (num_bits - 1)) - 1
        else:
            num_bytes = int(size_str.split()[0])
            if type_var.get() == "Unsigned":
                min_val, max_val = 0, (2 ** (8 * num_bytes)) - 1
            else:
                min_val, max_val = -(2 ** (8 * num_bytes - 1)), (2 ** (8 * num_bytes - 1)) - 1
        slider.config(from_=min_val, to=max_val)
        current_val = param_value_var.get()
        if current_val < min_val or current_val > max_val:
            param_value_var.set(min_val)

    size_var.trace("w", update_slider_range)
    type_var.trace("w", update_slider_range)
    update_slider_range()

    # --- Cycle Time Field ---
    tk.Label(param_win, text="Cycle Time (ms):").grid(row=7, column=0, sticky="w", padx=5, pady=2)
    cycle_time_entry = tk.Entry(param_win)
    cycle_time_entry.insert(0, "1000")
    cycle_time_entry.grid(row=7, column=1, padx=5, pady=2)

    # Global variable for transmission job (for after() scheduling)
    param_win.transmit_job = None

    # --- Persistent PCAN Bus Retrieval ---
    def get_bus():
        if not hasattr(param_win, 'bus'):
            try:
                param_win.bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to initialize CAN bus: {e}")
                return None
        return param_win.bus

    # --- Function to compute the encoded CAN frame ---
    def get_encoded_message():
        try:
            can_id_str = can_id_entry.get().strip()
            if can_id_str.startswith("0x") or can_id_str.startswith("0X"):
                can_id = int(can_id_str, 16)
            else:
                can_id = int(can_id_str, 16)
        except ValueError:
            messagebox.showerror("Error", "Invalid CAN ID")
            return None

        try:
            resolution = float(resolution_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid resolution")
            return None

        raw_value = param_value_var.get() / resolution
        raw_value = int(round(raw_value))

        size_str = size_var.get()
        data_payload = [0] * 8
        if "bit" in size_str:
            param_bits = int(size_str.split()[0])
            if type_var.get() == "Unsigned":
                bin_str = format(raw_value, f"0{param_bits}b")
            else:
                if raw_value < 0:
                    raw_value = (1 << param_bits) + raw_value
                bin_str = format(raw_value, f"0{param_bits}b")
            byte_val = 0
            for i, var in enumerate(mapping_frame.mapping_vars):
                bit_pos = int(var.get())
                bit_val = int(bin_str[i])
                if bit_val:
                    byte_val |= (1 << bit_pos)
            data_payload[0] = byte_val
        else:
            num_bytes = int(size_str.split()[0])
            if type_var.get() == "Signed" and raw_value < 0:
                raw_value = (1 << (8 * num_bytes)) + raw_value
            try:
                param_bytes = list(raw_value.to_bytes(num_bytes, byteorder='little', signed=False))
            except OverflowError:
                messagebox.showerror("Error", "Value out of range for the specified size")
                return None
            for i, var in enumerate(mapping_frame.mapping_vars):
                byte_pos = int(var.get())
                if 0 <= byte_pos < 8:
                    data_payload[byte_pos] = param_bytes[i]
        return (can_id, data_payload)

    # --- Functions for Transmission ---
    def send_once():
        encoded = get_encoded_message()
        if encoded is None:
            return
        can_id, data_payload = encoded
        bus = get_bus()
        if bus is None:
            return
        message = can.Message(arbitration_id=can_id, data=data_payload, is_extended_id=(can_id > 0x7FF))
        try:
            bus.send(message)
            result_str = " ".join(f"{b:02X}" for b in data_payload)
            messagebox.showinfo("Success", f"Message sent.\nCAN ID: {can_id_entry.get().strip()}\nData: {result_str}")
        except can.CanError as e:
            messagebox.showerror("CAN Error", f"Failed to send message: {e}")

    def transmit_message():
        encoded = get_encoded_message()
        if encoded is None:
            return
        can_id, data_payload = encoded
        bus = get_bus()
        if bus is None:
            return
        message = can.Message(arbitration_id=can_id, data=data_payload, is_extended_id=(can_id > 0x7FF))
        try:
            bus.send(message)
        except can.CanError as e:
            messagebox.showerror("CAN Error", f"Failed to send message: {e}")
        try:
            cycle_time_ms = float(cycle_time_entry.get())
        except ValueError:
            cycle_time_ms = 1000
        param_win.transmit_job = param_win.after(int(cycle_time_ms), transmit_message)

    def start_transmission():
        if param_win.transmit_job is None:
            transmit_message()

    def stop_transmission():
        if param_win.transmit_job is not None:
            param_win.after_cancel(param_win.transmit_job)
            param_win.transmit_job = None
        # Shut down the persistent bus if it exists.
        if hasattr(param_win, 'bus'):
            try:
                param_win.bus.shutdown()
            except Exception as e:
                messagebox.showerror("Error", f"Error during bus shutdown: {e}")
            del param_win.bus

    # --- Buttons for Sending ---
    btn_frame = tk.Frame(param_win)
    btn_frame.grid(row=8, column=0, columnspan=3, pady=10)
    send_once_btn = tk.Button(btn_frame, text="Send Once", command=send_once, width=15)
    send_once_btn.grid(row=0, column=0, padx=5)
    start_btn = tk.Button(btn_frame, text="Start Transmission", command=start_transmission, width=15)
    start_btn.grid(row=0, column=1, padx=5)
    stop_btn = tk.Button(btn_frame, text="Stop Transmission", command=stop_transmission, width=15)
    stop_btn.grid(row=0, column=2, padx=5)

# --- Main Window Setup ---
root = tk.Tk()
root.title("CAN Parameter Creator")
create_button = tk.Button(root, text="Create Parameter", command=create_parameter_window, width=20)
create_button.pack(pady=20)
root.mainloop()
