import can

def send_can_message():
    # Initialize the CAN bus using the 'pcan' interface.
    try:
        bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
    except Exception as e:
        print("Failed to initialize CAN bus:", e)
        return

    # Create a CAN message.
    message = can.Message(
        arbitration_id=0x00000008,         # The CAN ID
        data=[0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88],       # Up to 8 data bytes
        is_extended_id=False          # Use 'is_extended_id' instead of 'extended_id'
    )

    # Attempt to send the message.
    try:
        bus.send(message)
        print("Message sent on", bus.channel_info)
    except can.CanError:
        print("Failed to send message")

if __name__ == '__main__':
    send_can_message()
