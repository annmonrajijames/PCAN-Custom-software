import can

def send_can_message():
    try:
        bus = can.interface.Bus(interface='pcan', channel='PCAN_USBBUS1', bitrate=500000)
    except Exception as e:
        print("Failed to initialize CAN bus:", e)
        return

    # Using binary literals (each value is an integer)
    message = can.Message(
        arbitration_id=0b0000000000001000,  # Same as 0x00000008
        data=[
            0b00010001,  # Same as 0x11
            0b00100010,  # Same as 0x22
            0b00110011,  # Same as 0x33
            0b01000100,  # Same as 0x44
            0b01010101,  # Same as 0x55
            0b01100110,  # Same as 0x66
            0b01110111,  # Same as 0x77
            0b10001000   # Same as 0x88
        ],
        is_extended_id=False
    )

    try:
        bus.send(message)
        print("Message sent on", bus.channel_info)
    except can.CanError:
        print("Failed to send message")

if __name__ == '__main__':
    send_can_message()