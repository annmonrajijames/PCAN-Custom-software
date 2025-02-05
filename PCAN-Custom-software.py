import can
import time
import threading

def send_message(bus, message, cycle_time_sec, stop_event, label):
    """
    Sends a given CAN message repeatedly on the provided bus with a specified delay.
    The loop runs until the stop_event is set.
    """
    while not stop_event.is_set():
        try:
            bus.send(message)
            print(f"{label} sent on", bus.channel_info)
        except can.CanError as e:
            print(f"Failed to send {label}:", e)
        time.sleep(cycle_time_sec)

def main():
    # Initialize the CAN bus using the 'pcan' interface.
    try:
        bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
    except Exception as e:
        print("Failed to initialize CAN bus:", e)
        return

    # Message 1: Standard CAN frame with ID 0x08
    message1 = can.Message(
        arbitration_id=0b0000000000001000,  # 0x08 in binary
        data=[
            0b00010001,  # 0x11
            0b00000000,  # 0x00
            0b00000000,  # 0x00
            0b00000000,  # 0x00
            0b00000000,  # 0x00
            0b00000000,  # 0x00
            0b00000000,  # 0x00
            0b00000000   # 0x00
        ],
        is_extended_id=False  # Standard frame
    )

    # Message 2: Extended CAN frame with ID 0x18530902
    message2 = can.Message(
        arbitration_id=0x18530902,  # Extended CAN ID
        data=[
            0b00000000,
            0b00100100,
            0b00000000,
            0b00000000,
            0b00000000,
            0b00000000,
            0b00000000,
            0b00000000
        ],
        is_extended_id=True  # Extended frame
    )

    # Define cycle times in seconds.
    cycle_time1_sec = 250 / 1000.0  # 250 milliseconds for message 1
    cycle_time2_sec = 100 / 1000.0  # 100 milliseconds for message 2

    # Create an event to signal the threads to stop.
    stop_event = threading.Event()

    # Create and start threads for sending the two messages.
    thread1 = threading.Thread(
        target=send_message,
        args=(bus, message1, cycle_time1_sec, stop_event, "Message 1 (0x08)")
    )
    thread2 = threading.Thread(
        target=send_message,
        args=(bus, message2, cycle_time2_sec, stop_event, "Message 2 (0x18530902)")
    )

    thread1.start()
    thread2.start()

    print("Transmitting messages. Press Ctrl+C to stop.")

    # Wait until the user presses Ctrl+C.
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping transmissions...")
        stop_event.set()
        thread1.join()
        thread2.join()
        print("Transmission stopped.")

if __name__ == '__main__':
    main()
