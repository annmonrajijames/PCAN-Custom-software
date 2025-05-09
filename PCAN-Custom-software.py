import tkinter as tk
from tkinter import ttk, messagebox
import can

# ---------- Global PCAN Bus and Transmissions ----------
global_bus = None
def get_global_bus():
    global global_bus
    if global_bus is None:
        try:
            global_bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize CAN bus: {e}")
            return None
    return global_bus

# global_transmissions maps CAN IDs to:
#   {"cycle_time": cycle time (ms),
#    "params": [list of parameter functions],
#    "job": scheduled after() job}
global_transmissions = {}
def global_transmit(can_id):
    if can_id not in global_transmissions:
        return
    entry = global_transmissions[can_id]
    cycle_time_ms = entry["cycle_time"]
    combined_payload = [0] * 8
    for func in entry["params"]:
        payload = func()  # each function returns an 8-byte list
        for i in range(8):
            combined_payload[i] |= payload[i]
    bus = get_global_bus()
    if bus is not None:
        message = can.Message(arbitration_id=can_id,
                              data=combined_payload,
                              is_extended_id=(can_id > 0x7FF))
        try:
            bus.send(message)
            print(f"Sent CAN ID {hex(can_id)}: {' '.join(f'{b:02X}' for b in combined_payload)}")
        except can.CanError as e:
            print(f"CAN Error for {hex(can_id)}: {e}")
    job = root.after(int(cycle_time_ms), lambda: global_transmit(can_id))
    global_transmissions[can_id]["job"] = job

# ---------- Helper: Compute Slider Range (for Numeric Parameters) ----------
def compute_slider_range(config):
    if "min_value" in config and "max_value" in config:
        min_str = config["min_value"]
        max_str = config["max_value"]
        try:
            min_val = float(min_str)
            max_val = float(max_str)
        except:
            min_val, max_val = 0, 100
        if "." in max_str:
            precision = len(max_str.split(".")[1])
        else:
            precision = 0
        resolution_val = 10**(-precision) if precision > 0 else 1
        return min_val, max_val, resolution_val, precision
    else:
        size_str = config["size"]
        if "bit" in size_str:
            num_bits = int(size_str.split()[0])
            if config["type"] == "Unsigned":
                return 0, (2 ** num_bits) - 1, 1, 0
            else:
                return -(2 ** (num_bits - 1)), (2 ** (num_bits - 1)) - 1, 1, 0
        else:
            num_bytes = int(size_str.split()[0])
            if config["type"] == "Unsigned":
                return 0, (2 ** (8 * num_bytes)) - 1, 1, 0
            else:
                return -(2 ** (8 * num_bytes - 1)), (2 ** (8 * num_bytes - 1)) - 1, 1, 0

# ==================== Numeric Parameter ====================
class SavedParameter:
    def __init__(self, parent, config):
        """
        config keys:
          name, can_id, size, type, resolution, mapping (list), 
          target_byte (if bit), cycle_time, min_value, max_value, initial_value, mode ("numeric")
        """
        self.parent = parent
        self.config = config.copy()
        self.enabled = False
        self.value_var = tk.DoubleVar(value=config.get("initial_value", 0))
        try:
            min_val, max_val, res, prec = compute_slider_range(config)
        except Exception:
            min_val, max_val, res, prec = 0, 100, 1, 0
        self.frame = tk.Frame(parent, bd=2, relief=tk.GROOVE, padx=5, pady=5)
        self.label = tk.Label(self.frame, text=f"{config['name']} (CAN ID: {hex(config['can_id'])})")
        self.label.grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(self.frame, text="Value:").grid(row=1, column=0, sticky="w")
        self.slider = tk.Scale(self.frame, variable=self.value_var,
                               from_=min_val, to=max_val, resolution=res, orient=tk.HORIZONTAL)
        self.slider.grid(row=1, column=1, sticky="we")
        self.entry = tk.Entry(self.frame, textvariable=self.value_var, width=10)
        self.entry.grid(row=1, column=2, sticky="e")
        tk.Label(self.frame, text="Cycle Time (ms):").grid(row=2, column=0, sticky="w")
        self.cycle_time_var = tk.StringVar(value=str(config.get("cycle_time", 1000)))
        self.cycle_time_entry = tk.Entry(self.frame, textvariable=self.cycle_time_var, width=8)
        self.cycle_time_entry.grid(row=2, column=1, sticky="we")
        self.cycle_time_entry.bind("<FocusOut>", self.update_cycle_time)
        self.enable_button = tk.Button(self.frame, text="Enable", command=self.toggle_enable, width=10)
        self.enable_button.grid(row=3, column=0, padx=5, pady=5)
        self.edit_button = tk.Button(self.frame, text="Edit", command=self.edit, width=10)
        self.edit_button.grid(row=3, column=1, padx=5, pady=5)
        self.frame.pack(fill="x", padx=5, pady=5)
    def get_payload(self):
        size_str = self.config["size"]
        resolution = self.config["resolution"]
        raw_value = self.value_var.get() / resolution
        raw_value = int(round(raw_value))
        data_payload = [0] * 8
        if "bit" in size_str:
            num_bits = int(size_str.split()[0])
            if self.config["type"] == "Unsigned":
                bin_str = format(raw_value, f"0{num_bits}b")
            else:
                if raw_value < 0:
                    raw_value = (1 << num_bits) + raw_value
                bin_str = format(raw_value, f"0{num_bits}b")
            byte_val = 0
            for i, bit_pos in enumerate(self.config["mapping"]):
                if int(bin_str[i]):
                    byte_val |= (1 << bit_pos)
            target_byte = self.config["target_byte"]
            data_payload[target_byte] = byte_val
        else:
            num_bytes = int(size_str.split()[0])
            if self.config["type"] == "Signed" and raw_value < 0:
                raw_value = (1 << (8 * num_bytes)) + raw_value
            try:
                param_bytes = list(raw_value.to_bytes(num_bytes, byteorder='little', signed=False))
            except OverflowError:
                return [0] * 8
            for i, byte_pos in enumerate(self.config["mapping"]):
                if 0 <= byte_pos < 8:
                    data_payload[byte_pos] = param_bytes[i]
        return data_payload
    def update_cycle_time(self, event=None):
        try:
            new_cycle_time = float(self.cycle_time_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid cycle time")
            return
        self.config["cycle_time"] = new_cycle_time
        if self.enabled:
            can_id = self.config["can_id"]
            if can_id in global_transmissions:
                global_transmissions[can_id]["cycle_time"] = new_cycle_time
                if global_transmissions[can_id]["job"]:
                    root.after_cancel(global_transmissions[can_id]["job"])
                global_transmit(can_id)
                print(f"Updated cycle time for CAN ID {hex(can_id)} to {new_cycle_time} ms.")
    def toggle_enable(self):
        if not self.enabled:
            try:
                cycle_time_ms = float(self.cycle_time_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid cycle time")
                return
            can_id = self.config["can_id"]
            def param_func():
                return self.get_payload()
            self.param_func = param_func
            print(f"Enabling parameter '{self.config['name']}' on CAN ID {hex(can_id)} with cycle time {cycle_time_ms} ms.")
            if can_id in global_transmissions:
                if global_transmissions[can_id]["cycle_time"] != cycle_time_ms:
                    global_transmissions[can_id]["cycle_time"] = cycle_time_ms
                    for sp in saved_parameters:
                        if sp.enabled and sp.config["can_id"] == can_id:
                            sp.cycle_time_var.set(str(cycle_time_ms))
                    if global_transmissions[can_id]["job"]:
                        root.after_cancel(global_transmissions[can_id]["job"])
                    global_transmit(can_id)
                global_transmissions[can_id]["params"].append(param_func)
            else:
                global_transmissions[can_id] = {"cycle_time": cycle_time_ms, "params": [param_func], "job": None}
                global_transmit(can_id)
            self.enabled = True
            self.enable_button.config(text="Disable")
        else:
            can_id = self.config["can_id"]
            if can_id in global_transmissions:
                try:
                    global_transmissions[can_id]["params"].remove(self.param_func)
                    print(f"Disabling parameter '{self.config['name']}' on CAN ID {hex(can_id)}.")
                except ValueError:
                    pass
                if not global_transmissions[can_id]["params"]:
                    if global_transmissions[can_id]["job"]:
                        root.after_cancel(global_transmissions[can_id]["job"])
                    del global_transmissions[can_id]
            self.enabled = False
            self.enable_button.config(text="Enable")
    def edit(self):
        open_parameter_editor(self)

# ==================== ASCII Parameter ====================
class ASCIISavedParameter:
    def __init__(self, parent, config):
        """
        config keys:
          name, can_id, size, mapping (list), cycle_time, mode ("ascii"),
          initial_value (a string)
        For ASCII parameters, size is "X byte" and mapping is a list of target byte positions.
        """
        self.parent = parent
        self.config = config.copy()
        self.enabled = False
        self.value_var = tk.StringVar(value=config.get("initial_value", ""))
        self.expected_length = int(config["size"].split()[0])
        self.frame = tk.Frame(parent, bd=2, relief=tk.GROOVE, padx=5, pady=5)
        self.label = tk.Label(self.frame, text=f"{config['name']} (CAN ID: {hex(config['can_id'])})")
        self.label.grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(self.frame, text="Value:").grid(row=1, column=0, sticky="w")
        self.entry = tk.Entry(self.frame, textvariable=self.value_var, width=10)
        self.entry.grid(row=1, column=1, sticky="we")
        tk.Label(self.frame, text=f"(max {self.expected_length} chars)").grid(row=1, column=2, sticky="w")
        tk.Label(self.frame, text="Cycle Time (ms):").grid(row=2, column=0, sticky="w")
        self.cycle_time_var = tk.StringVar(value=str(config.get("cycle_time", 1000)))
        self.cycle_time_entry = tk.Entry(self.frame, textvariable=self.cycle_time_var, width=8)
        self.cycle_time_entry.grid(row=2, column=1, sticky="we")
        self.cycle_time_entry.bind("<FocusOut>", self.update_cycle_time)
        self.enable_button = tk.Button(self.frame, text="Enable", command=self.toggle_enable, width=10)
        self.enable_button.grid(row=3, column=0, padx=5, pady=5)
        self.edit_button = tk.Button(self.frame, text="Edit", command=self.edit, width=10)
        self.edit_button.grid(row=3, column=1, padx=5, pady=5)
        self.frame.pack(fill="x", padx=5, pady=5)
    def get_payload(self):
        data_payload = [0] * 8
        text = self.value_var.get()
        text = (text + " " * self.expected_length)[:self.expected_length]
        for i, byte_pos in enumerate(self.config["mapping"]):
            if i < len(text):
                data_payload[int(byte_pos)] = ord(text[i])
        return data_payload
    def update_cycle_time(self, event=None):
        try:
            new_cycle_time = float(self.cycle_time_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid cycle time")
            return
        self.config["cycle_time"] = new_cycle_time
        if self.enabled:
            can_id = self.config["can_id"]
            if can_id in global_transmissions:
                global_transmissions[can_id]["cycle_time"] = new_cycle_time
                if global_transmissions[can_id]["job"]:
                    root.after_cancel(global_transmissions[can_id]["job"])
                global_transmit(can_id)
                print(f"Updated cycle time for CAN ID {hex(can_id)} to {new_cycle_time} ms.")
    def toggle_enable(self):
        if not self.enabled:
            try:
                cycle_time_ms = float(self.cycle_time_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid cycle time")
                return
            can_id = self.config["can_id"]
            def param_func():
                return self.get_payload()
            self.param_func = param_func
            print(f"Enabling ASCII parameter '{self.config['name']}' on CAN ID {hex(can_id)} with cycle time {cycle_time_ms} ms.")
            if can_id in global_transmissions:
                if global_transmissions[can_id]["cycle_time"] != cycle_time_ms:
                    global_transmissions[can_id]["cycle_time"] = cycle_time_ms
                    for sp in saved_parameters:
                        if sp.enabled and sp.config["can_id"] == can_id:
                            sp.cycle_time_var.set(str(cycle_time_ms))
                    if global_transmissions[can_id]["job"]:
                        root.after_cancel(global_transmissions[can_id]["job"])
                    global_transmit(can_id)
                global_transmissions[can_id]["params"].append(param_func)
            else:
                global_transmissions[can_id] = {"cycle_time": cycle_time_ms, "params": [param_func], "job": None}
                global_transmit(can_id)
            self.enabled = True
            self.enable_button.config(text="Disable")
        else:
            can_id = self.config["can_id"]
            if can_id in global_transmissions:
                try:
                    global_transmissions[can_id]["params"].remove(self.param_func)
                    print(f"Disabling ASCII parameter '{self.config['name']}' on CAN ID {hex(can_id)}.")
                except ValueError:
                    pass
                if not global_transmissions[can_id]["params"]:
                    if global_transmissions[can_id]["job"]:
                        root.after_cancel(global_transmissions[can_id]["job"])
                    del global_transmissions[can_id]
            self.enabled = False
            self.enable_button.config(text="Enable")
    def edit(self):
        open_ascii_parameter_editor(self)

# ---------- Numeric Parameter Editor ----------
def open_parameter_editor(saved_param=None):
    editor = tk.Toplevel(root)
    editor.title("Parameter Editor")
    tk.Label(editor, text="Parameter Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    name_entry = tk.Entry(editor)
    name_entry.grid(row=0, column=1, padx=5, pady=2)
    tk.Label(editor, text="CAN ID (hex):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    can_id_entry = tk.Entry(editor)
    can_id_entry.grid(row=1, column=1, padx=5, pady=2)
    tk.Label(editor, text="Parameter Size:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    size_options = [
        "1 bit", "2 bit", "3 bit", "4 bit", "5 bit", "6 bit", "7 bit", "8 bit",
        "2 byte", "3 byte", "4 byte", "5 byte", "6 byte", "7 byte", "8 byte"
    ]
    size_var = tk.StringVar(value=size_options[0])
    size_menu = ttk.Combobox(editor, textvariable=size_var, values=size_options, state="readonly", width=10)
    size_menu.grid(row=2, column=1, padx=5, pady=2)
    tk.Label(editor, text="Parameter Type:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
    type_options = ["Unsigned", "Signed"]
    type_var = tk.StringVar(value=type_options[0])
    type_menu = ttk.Combobox(editor, textvariable=type_var, values=type_options, state="readonly", width=10)
    type_menu.grid(row=3, column=1, padx=5, pady=2)
    tk.Label(editor, text="Resolution:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
    resolution_entry = tk.Entry(editor)
    resolution_entry.insert(0, "1")
    resolution_entry.grid(row=4, column=1, padx=5, pady=2)
    tk.Label(editor, text="Minimum Value:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
    min_val_entry = tk.Entry(editor)
    min_val_entry.insert(0, "0")
    min_val_entry.grid(row=5, column=1, padx=5, pady=2)
    tk.Label(editor, text="Maximum Value:").grid(row=6, column=0, sticky="w", padx=5, pady=2)
    max_val_entry = tk.Entry(editor)
    max_val_entry.insert(0, "100")
    max_val_entry.grid(row=6, column=1, padx=5, pady=2)
    mapping_frame = tk.Frame(editor)
    mapping_frame.grid(row=7, column=0, columnspan=3, pady=10)
    def update_mapping_options(*args):
        for widget in mapping_frame.winfo_children():
            widget.destroy()
        size_str = size_var.get()
        mapping_vars = []
        if "bit" in size_str:
            num_bits = int(size_str.split()[0])
            tk.Label(mapping_frame, text="Select Bit Positions (order):").grid(row=0, column=0, columnspan=num_bits)
            for i in range(num_bits):
                default_value = str(num_bits - 1 - i)
                var = tk.StringVar(value=default_value)
                mapping_vars.append(var)
                bit_menu = ttk.Combobox(mapping_frame, textvariable=var, values=[str(x) for x in range(8)],
                                        state="readonly", width=3)
                bit_menu.grid(row=1, column=i, padx=2)
        else:
            num_bytes = int(size_str.split()[0])
            tk.Label(mapping_frame, text="Select Byte Positions (order):").grid(row=0, column=0, columnspan=num_bytes)
            for i in range(num_bytes):
                default_value = str(num_bytes - 1 - i)
                var = tk.StringVar(value=default_value)
                mapping_vars.append(var)
                byte_menu = ttk.Combobox(mapping_frame, textvariable=var, values=[str(x) for x in range(8)],
                                         state="readonly", width=3)
                byte_menu.grid(row=1, column=i, padx=2)
        mapping_frame.mapping_vars = mapping_vars
    size_var.trace("w", update_mapping_options)
    update_mapping_options()
    bit_target_var = tk.StringVar(value="0")
    bit_target_label = tk.Label(editor, text="Target Byte for Bit Parameter:")
    bit_target_combo = ttk.Combobox(editor, textvariable=bit_target_var, values=[str(x) for x in range(8)],
                                    state="readonly", width=10)
    def update_bit_target_visibility(*args):
        if "bit" in size_var.get():
            bit_target_label.grid(row=8, column=0, sticky="w", padx=5, pady=2)
            bit_target_combo.grid(row=8, column=1, padx=5, pady=2)
        else:
            bit_target_label.grid_forget()
            bit_target_combo.grid_forget()
    size_var.trace("w", update_bit_target_visibility)
    update_bit_target_visibility()
    tk.Label(editor, text="Parameter Value:").grid(row=9, column=0, sticky="w", padx=5, pady=2)
    value_var = tk.DoubleVar(value=0)
    def update_slider_range(*args):
        try:
            min_str = min_val_entry.get()
            max_str = max_val_entry.get()
            min_val = float(min_str)
            max_val = float(max_str)
            if "." in max_str:
                precision = len(max_str.split(".")[1])
            else:
                precision = 0
            res = 10**(-precision) if precision > 0 else 1
        except ValueError:
            min_val, max_val, res, precision = 0, 100, 1, 0
        slider.config(from_=min_val, to=max_val, resolution=res)
        cur_val = value_var.get()
        if cur_val < min_val or cur_val > max_val:
            value_var.set(min_val)
    slider = tk.Scale(editor, variable=value_var, from_=0, to=100, orient=tk.HORIZONTAL)
    slider.grid(row=9, column=1, padx=5, pady=2, sticky="we")
    entry = tk.Entry(editor, textvariable=value_var, width=10)
    entry.grid(row=9, column=2, padx=5, pady=2)
    min_val_entry.bind("<FocusOut>", lambda e: update_slider_range())
    max_val_entry.bind("<FocusOut>", lambda e: update_slider_range())
    size_var.trace("w", update_slider_range)
    type_var.trace("w", update_slider_range)
    update_slider_range()
    tk.Label(editor, text="Cycle Time (ms):").grid(row=10, column=0, sticky="w", padx=5, pady=2)
    cycle_time_entry = tk.Entry(editor)
    cycle_time_entry.insert(0, "1000")
    cycle_time_entry.grid(row=10, column=1, padx=5, pady=2)
    if saved_param:
        config = saved_param.config
        name_entry.insert(0, config["name"])
        can_id_entry.insert(0, hex(config["can_id"])[2:])
        size_var.set(config["size"])
        type_var.set(config["type"])
        resolution_entry.delete(0, tk.END)
        resolution_entry.insert(0, str(config["resolution"]))
        if "min_value" in config:
            min_val_entry.delete(0, tk.END)
            min_val_entry.insert(0, str(config["min_value"]))
        if "max_value" in config:
            max_val_entry.delete(0, tk.END)
            max_val_entry.insert(0, str(config["max_value"]))
        update_mapping_options()
        for i, var in enumerate(mapping_frame.mapping_vars):
            try:
                var.set(str(config["mapping"][i]))
            except IndexError:
                break
        if "bit" in config["size"]:
            bit_target_var.set(str(config["target_byte"]))
        value_var.set(saved_param.value_var.get())
        cycle_time_entry.delete(0, tk.END)
        cycle_time_entry.insert(0, str(saved_param.cycle_time_var.get()))
    def save_edits():
        try:
            can_id_str = can_id_entry.get().strip()
            if can_id_str.startswith("0x") or can_id_str.startswith("0X"):
                can_id = int(can_id_str, 16)
            else:
                can_id = int(can_id_str, 16)
        except ValueError:
            messagebox.showerror("Error", "Invalid CAN ID")
            return
        try:
            min_value = min_val_entry.get()
            max_value = max_val_entry.get()
            float(min_value)
            float(max_value)
        except ValueError:
            messagebox.showerror("Error", "Invalid minimum or maximum value")
            return
        new_config = {
            "name": name_entry.get().strip(),
            "can_id": can_id,
            "size": size_var.get(),
            "type": type_var.get(),
            "resolution": float(resolution_entry.get()),
            "mapping": [int(var.get()) for var in mapping_frame.mapping_vars],
            "cycle_time": float(cycle_time_entry.get()),
            "min_value": min_value,
            "max_value": max_value,
            "mode": "numeric"
        }
        if "bit" in size_var.get():
            new_config["target_byte"] = int(bit_target_var.get())
        if saved_param:
            saved_param.config = new_config
            saved_param.cycle_time_var.set(str(new_config["cycle_time"]))
            saved_param.label.config(text=f"{new_config['name']} (CAN ID: {hex(new_config['can_id'])})")
            min_val, max_val, res, prec = compute_slider_range(new_config)
            saved_param.slider.config(from_=min_val, to=max_val, resolution=res)
        else:
            new_config["initial_value"] = value_var.get()
            add_saved_parameter(new_config)
        editor.destroy()
    save_button = tk.Button(editor, text="Save", command=save_edits)
    save_button.grid(row=11, column=0, columnspan=3, pady=10)

def add_saved_parameter(config):
    sp = SavedParameter(saved_parameters_frame, config)
    saved_parameters.append(sp)

# =================== ASCII Parameter Editor ===================
def open_ascii_parameter_editor(saved_param=None):
    editor = tk.Toplevel(root)
    editor.title("ASCII Parameter Editor")
    tk.Label(editor, text="Parameter Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    name_entry = tk.Entry(editor)
    name_entry.grid(row=0, column=1, padx=5, pady=2)
    tk.Label(editor, text="CAN ID (hex):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    can_id_entry = tk.Entry(editor)
    can_id_entry.grid(row=1, column=1, padx=5, pady=2)
    tk.Label(editor, text="Parameter Size:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    size_options = ["1 byte", "2 byte", "3 byte", "4 byte", "5 byte", "6 byte", "7 byte", "8 byte"]
    size_var = tk.StringVar(value=size_options[0])
    size_menu = ttk.Combobox(editor, textvariable=size_var, values=size_options, state="readonly", width=10)
    size_menu.grid(row=2, column=1, padx=5, pady=2)
    mapping_frame = tk.Frame(editor)
    mapping_frame.grid(row=3, column=0, columnspan=3, pady=10)
    def update_mapping_options(*args):
        for widget in mapping_frame.winfo_children():
            widget.destroy()
        size_str = size_var.get()
        num_bytes = int(size_str.split()[0])
        tk.Label(mapping_frame, text="Select Byte Positions (order):").grid(row=0, column=0, columnspan=num_bytes)
        mapping_vars = []
        for i in range(num_bytes):
            default_value = str(num_bytes - 1 - i)
            var = tk.StringVar(value=default_value)
            mapping_vars.append(var)
            byte_menu = ttk.Combobox(mapping_frame, textvariable=var, values=[str(x) for x in range(8)],
                                     state="readonly", width=3)
            byte_menu.grid(row=1, column=i, padx=2)
        mapping_frame.mapping_vars = mapping_vars
    size_var.trace("w", update_mapping_options)
    update_mapping_options()
    tk.Label(editor, text="Parameter Value:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
    value_entry = tk.Entry(editor, width=10)
    value_entry.grid(row=4, column=1, padx=5, pady=2)
    def enforce_length(*args):
        expected = int(size_var.get().split()[0])
        text = value_entry.get()
        if len(text) > expected:
            value_entry.delete(expected, tk.END)
    value_entry.bind("<KeyRelease>", lambda e: enforce_length())
    tk.Label(editor, text="Cycle Time (ms):").grid(row=5, column=0, sticky="w", padx=5, pady=2)
    cycle_time_entry = tk.Entry(editor)
    cycle_time_entry.insert(0, "1000")
    cycle_time_entry.grid(row=5, column=1, padx=5, pady=2)
    if saved_param:
        config = saved_param.config
        name_entry.insert(0, config["name"])
        can_id_entry.insert(0, hex(config["can_id"])[2:])
        size_var.set(config["size"])
        update_mapping_options()
        for i, var in enumerate(mapping_frame.mapping_vars):
            try:
                var.set(str(config["mapping"][i]))
            except IndexError:
                break
        value_entry.delete(0, tk.END)
        value_entry.insert(0, config.get("initial_value", ""))
        cycle_time_entry.delete(0, tk.END)
        cycle_time_entry.insert(0, str(config.get("cycle_time", 1000)))
    def save_edits():
        try:
            can_id_str = can_id_entry.get().strip()
            if can_id_str.startswith("0x") or can_id_str.startswith("0X"):
                can_id = int(can_id_str, 16)
            else:
                can_id = int(can_id_str, 16)
        except ValueError:
            messagebox.showerror("Error", "Invalid CAN ID")
            return
        new_config = {
            "name": name_entry.get().strip(),
            "can_id": can_id,
            "size": size_var.get(),
            "mapping": [int(var.get()) for var in mapping_frame.mapping_vars],
            "cycle_time": float(cycle_time_entry.get()),
            "mode": "ascii",
            "initial_value": value_entry.get()
        }
        if saved_param:
            saved_param.config = new_config
            saved_param.cycle_time_var.set(str(new_config["cycle_time"]))
            saved_param.label.config(text=f"{new_config['name']} (CAN ID: {hex(new_config['can_id'])})")
            saved_param.expected_length = int(new_config["size"].split()[0])
        else:
            add_ascii_saved_parameter(new_config)
        editor.destroy()
    save_button = tk.Button(editor, text="Save", command=save_edits)
    save_button.grid(row=6, column=0, columnspan=3, pady=10)

def add_ascii_saved_parameter(config):
    sp = ASCIISavedParameter(saved_parameters_frame, config)
    saved_parameters.append(sp)

# ================= Main Window Setup =================
root = tk.Tk()
root.title("CAN Parameter Creator")
top_frame = tk.Frame(root)
top_frame.pack(pady=10)
create_numeric_button = tk.Button(top_frame, text="Create Parameter", command=open_parameter_editor, width=20)
create_numeric_button.pack(side="left", padx=5)
create_ascii_button = tk.Button(top_frame, text="Create ASCII parameter", command=open_ascii_parameter_editor, width=20)
create_ascii_button.pack(side="left", padx=5)
saved_parameters_frame = tk.LabelFrame(root, text="Saved Parameters", padx=5, pady=5)
saved_parameters_frame.pack(fill="both", expand=True, padx=10, pady=10)
saved_parameters = []  # Combined list for both numeric and ASCII parameters.
def on_closing():
    for can_id in list(global_transmissions.keys()):
        if global_transmissions[can_id]["job"]:
            root.after_cancel(global_transmissions[can_id]["job"])
    global global_bus
    if global_bus is not None:
        try:
            global_bus.shutdown()
        except Exception as e:
            print("Error during bus shutdown:", e)
    root.destroy()
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
