import can
import time

def send_can_message_repeatedly():
    # Initialize the CAN bus using the 'pcan' interface.
    try:
        bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
    except Exception as e:
        print("Failed to initialize CAN bus:", e)
        return

    # Hardcoded data bytes (each provided as a binary literal).
    data = [
        0b00010001,  # Same as 0x11
        0b00000000,  # Same as 0x00
        0b00000000,  # Same as 0x00
        0b00000000,  # Same as 0x00
        0b00000000,  # Same as 0x00
        0b00000000,  # Same as 0x00
        0b00000000,  # Same as 0x00
        0b00000000   # Same as 0x00
    ]
    
    # Define the cycle time in milliseconds here.
    cycle_time_ms = 1000  # e.g., 1000 ms (1 second)
    cycle_time_sec = cycle_time_ms / 1000.0

    # Create a CAN message.
    message = can.Message(
        arbitration_id=0b0000000000001000,  # Example CAN ID (binary literal; same as 0x08)
        data=data,
        is_extended_id=False
    )

    print(f"Sending message every {cycle_time_ms} ms. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                bus.send(message)
                print("Message sent on", bus.channel_info)
            except can.CanError as e:
                print("Failed to send message:", e)
            time.sleep(cycle_time_sec)
    except KeyboardInterrupt:
        print("Cycle transmission stopped by user.")

if __name__ == '__main__':
    send_can_message_repeatedly()
