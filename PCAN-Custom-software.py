import tkinter as tk
from tkinter import ttk, messagebox
import can

# --- This function creates the parameter configuration window ---
def create_parameter_window():
    param_win = tk.Toplevel(root)
    param_win.title("Create Parameter")

    # Parameter name field
    tk.Label(param_win, text="Parameter Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    param_name_entry = tk.Entry(param_win)
    param_name_entry.grid(row=0, column=1, padx=5, pady=2)

    # CAN ID entry (hexadecimal)
    tk.Label(param_win, text="CAN ID (hex):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    can_id_entry = tk.Entry(param_win)
    can_id_entry.grid(row=1, column=1, padx=5, pady=2)

    # Parameter Size selection
    tk.Label(param_win, text="Parameter Size:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    size_options = [
        "1 bit", "2 bit", "3 bit", "4 bit", "5 bit", "6 bit", "7 bit", "8 bit",
        "2 byte", "3 byte", "4 byte", "5 byte", "6 byte", "7 byte", "8 byte"
    ]
    size_var = tk.StringVar(value=size_options[0])
    size_menu = ttk.Combobox(param_win, textvariable=size_var, values=size_options, state="readonly", width=10)
    size_menu.grid(row=2, column=1, padx=5, pady=2)

    # Parameter Type selection: Signed or Unsigned
    tk.Label(param_win, text="Parameter Type:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
    type_options = ["Unsigned", "Signed"]
    type_var = tk.StringVar(value=type_options[0])
    type_menu = ttk.Combobox(param_win, textvariable=type_var, values=type_options, state="readonly", width=10)
    type_menu.grid(row=3, column=1, padx=5, pady=2)

    # Resolution entry field
    tk.Label(param_win, text="Resolution:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
    resolution_entry = tk.Entry(param_win)
    resolution_entry.insert(0, "1")
    resolution_entry.grid(row=4, column=1, padx=5, pady=2)

    # Mapping frame: This area will hold the dropdowns to choose the bit/byte positions.
    mapping_frame = tk.Frame(param_win)
    mapping_frame.grid(row=5, column=0, columnspan=2, pady=10)

    # Update the mapping options based on the chosen size.
    def update_mapping_options(*args):
        # Remove any old widgets from the mapping frame.
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
                # Dropdown for each bit: options 0 through 7 (bit positions)
                bit_menu = ttk.Combobox(mapping_frame, textvariable=var, values=[str(x) for x in range(8)], state="readonly", width=3)
                bit_menu.grid(row=1, column=i, padx=2)
        else:
            # For byte parameters (e.g., "2 byte", "3 byte", etc.)
            num_bytes = int(size_str.split()[0])
            tk.Label(mapping_frame, text="Select Byte Positions (order):").grid(row=0, column=0, columnspan=num_bytes)
            for i in range(num_bytes):
                var = tk.StringVar(value="0")
                mapping_vars.append(var)
                # Dropdown for each byte: options 0 through 7 (byte positions)
                byte_menu = ttk.Combobox(mapping_frame, textvariable=var, values=[str(x) for x in range(8)], state="readonly", width=3)
                byte_menu.grid(row=1, column=i, padx=2)
        mapping_frame.mapping_vars = mapping_vars

    size_var.trace("w", update_mapping_options)
    update_mapping_options()  # initialize mapping options

    # Slider for parameter value
    tk.Label(param_win, text="Parameter Value:").grid(row=6, column=0, sticky="w", padx=5, pady=2)
    slider = tk.Scale(param_win, from_=0, to=100, orient=tk.HORIZONTAL)
    slider.grid(row=6, column=1, padx=5, pady=2)

    # Update the slider range based on parameter size and type.
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

    size_var.trace("w", update_slider_range)
    type_var.trace("w", update_slider_range)
    update_slider_range()

    # --- Function to encode the slider value into an 8-byte CAN frame ---
    def encode_parameter():
        # Retrieve and validate the CAN ID input.
        try:
            can_id_str = can_id_entry.get().strip()
            if can_id_str.startswith("0x") or can_id_str.startswith("0X"):
                can_id = int(can_id_str, 16)
            else:
                can_id = int(can_id_str, 16)
        except ValueError:
            messagebox.showerror("Error", "Invalid CAN ID")
            return

        # Read the resolution and calculate the raw (scaled) value.
        try:
            resolution = float(resolution_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid resolution")
            return

        # Get the slider value and divide by resolution
        raw_value = slider.get() / resolution
        raw_value = int(round(raw_value))

        size_str = size_var.get()
        data_payload = [0] * 8  # start with 8 zeroed bytes

        if "bit" in size_str:
            param_bits = int(size_str.split()[0])
            # For unsigned, simply format the value in binary with leading zeros.
            # For signed, use two's complement if necessary.
            if type_var.get() == "Unsigned":
                bin_str = format(raw_value, f"0{param_bits}b")
            else:
                if raw_value < 0:
                    raw_value = (1 << param_bits) + raw_value
                bin_str = format(raw_value, f"0{param_bits}b")
            # Map these bits into one byte based on the user-selected bit positions.
            byte_val = 0
            for i, var in enumerate(mapping_frame.mapping_vars):
                bit_pos = int(var.get())
                bit_val = int(bin_str[i])
                if bit_val:
                    byte_val |= (1 << bit_pos)
            data_payload[0] = byte_val  # here we assume the bit parameter is in byte 0

        else:
            # For byte parameters, determine how many bytes.
            num_bytes = int(size_str.split()[0])
            # For signed values, convert negative numbers to two's complement.
            if type_var.get() == "Signed" and raw_value < 0:
                raw_value = (1 << (8 * num_bytes)) + raw_value
            # Convert the raw value to a bytes object (little-endian is assumed)
            try:
                param_bytes = list(raw_value.to_bytes(num_bytes, byteorder='little', signed=False))
            except OverflowError:
                messagebox.showerror("Error", "Value out of range for the specified size")
                return
            # Map the parameter bytes into the data payload at the chosen byte positions.
            for i, var in enumerate(mapping_frame.mapping_vars):
                byte_pos = int(var.get())
                if 0 <= byte_pos < 8:
                    data_payload[byte_pos] = param_bytes[i]

        # For demonstration, show the resulting encoded CAN frame.
        result_str = " ".join(f"{b:02X}" for b in data_payload)
        messagebox.showinfo("Encoded CAN Frame", f"CAN ID: {can_id_str}\nData: {result_str}")

        # Optionally, to send via python-can (requires PCAN drivers and proper configuration):
        # bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
        # message = can.Message(arbitration_id=can_id, data=data_payload, is_extended_id=(can_id > 0x7FF))
        # try:
        #     bus.send(message)
        # except can.CanError as e:
        #     messagebox.showerror("CAN Error", f"Failed to send message: {e}")

    # Send button to encode (and optionally send) the parameter value.
    send_button = tk.Button(param_win, text="Send", command=encode_parameter)
    send_button.grid(row=7, column=0, columnspan=2, pady=10)

# --- Main Window Setup ---
root = tk.Tk()
root.title("CAN Parameter Creator")

create_button = tk.Button(root, text="Create Parameter", command=create_parameter_window, width=20)
create_button.pack(pady=20)

root.mainloop()
