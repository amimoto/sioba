import pytest

from nicegui import ui

from nicegui.testing import Screen

from sioba_nicegui.xterm import XTerm

def test_page(screen: Screen):

    # Make sure we have something to look at
    ui.label('XTerm Test!')

    global captured
    captured = b""

    def on_write(interface, data: bytes):
        global captured
        captured += data
        interface.read(data)

    interface = Interface(on_write=on_write)
    interface.start()
    xterm = XTerm(interface=interface)

    # Now on to the test!
    screen.open('/')
    screen.should_contain('XTerm Test!')

    # Click on the terminal
    elements = screen.find_all_by_class('sioba-xtermjs')
    screen.click_at_position(elements[0], 20, 100)

    # Send it some data
    send_buffer = 'echo "Hello, world!"'
    screen.type(send_buffer)

    # Validate that our server side controller received the data
    assert captured.decode() == send_buffer

    # Make sure we're not just passing things through
    send_buffer2 = "bananas"
    screen.type(send_buffer2)
    assert captured.decode() != send_buffer
    assert captured.decode() != send_buffer2
    assert captured.decode() == (send_buffer + send_buffer2)
