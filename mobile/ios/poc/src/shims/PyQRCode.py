"""PyQRCode shim for iOS (QR code generation not critical for PoC)."""


def create(*args, **kwargs):
    raise NotImplementedError("PyQRCode not available on iOS")


class QRCode:
    def __init__(self, *args, **kwargs):
        pass

    def png(self, *args, **kwargs):
        pass

    def svg(self, *args, **kwargs):
        pass
