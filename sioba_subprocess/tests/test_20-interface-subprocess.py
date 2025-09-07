from unittest import IsolatedAsyncioTestCase
from sioba import (
    interface_from_uri,
    InterfaceState,
)
from sioba_subprocess import (
    ShellInterface
)
import sys
import pathlib
import asyncio

class TestImportSubprocess(IsolatedAsyncioTestCase):

    async def invoke_subprocess(
            self,
            exec_uri: str = None,
            invoke_args: str = None,
            invoke_cwd: str = None,
            invoke_start_dwell: float = 1,
            expected_running: bool = True,
            expected_state: InterfaceState = InterfaceState.STARTED,
        ):
        # Find out where the path to python might be
        if exec_uri is None:
            invoke_command_fpath = sys.executable
            invoke_command_path = pathlib.Path(invoke_command_fpath)
            self.assertTrue(invoke_command_path.exists(), "Python executable path does not exist.")
            exec_uri = "exec:///"+str(invoke_command_path)

        # Construct the exec URI for the subprocess interface
        exec_interface = interface_from_uri(
            exec_uri,
            invoke_args=invoke_args,
            invoke_cwd=invoke_cwd,
        )
        await exec_interface.start()

        # Ensure we're started by waiting a teeny bit
        if invoke_start_dwell:
            await asyncio.sleep(invoke_start_dwell)

        self.assertEqual(exec_interface.state, expected_state)
        self.assertIsInstance(exec_interface, ShellInterface)
        self.assertEqual(exec_interface.is_running(), expected_running)

        return exec_interface

    async def test_subprocess_invoke_minimal(self):
        invoke_command_fpath = sys.executable
        invoke_command_path = pathlib.Path(invoke_command_fpath)
        self.assertTrue(invoke_command_path.exists(), "Python executable path does not exist.")
        exec_uri = "exec:///"+str(invoke_command_path)

        # Construct the exec URI for the subprocess interface
        exec_interface = interface_from_uri(exec_uri)

        from sioba_subprocess.interface import ShellInterface, ShellContext
        self.assertIsInstance(exec_interface, ShellInterface)
        self.assertEqual(exec_interface.context_class, ShellContext)
        self.assertIsInstance(exec_interface.context, ShellContext)

        await exec_interface.start()

    async def test_subprocess_invoke(self):
        """ Invoke and start a subprocess interface and do some IO
        """

        # Find out where the path to python might be
        exec_interface = await self.invoke_subprocess()

        # Let's compute the md5 hash of "hello world" using python. We force
        # a quick computation to ensure that we aren't just checking the for the
        # input
        await exec_interface.receive_from_frontend(b"import hashlib\n")
        await exec_interface.receive_from_frontend(b'hashlib.md5(b"hello world").hexdigest()\n')
        await asyncio.sleep(0.5)

        # Now let's check if we received the output
        buffer = exec_interface.buffer.dump_screen_state().decode()
        self.assertIn("5eb63bbbe01eeed093cb22bb8f5acdc3", buffer)

        # Let's exit the python process
        await exec_interface.receive_from_frontend(b"exit()\n")
        await asyncio.sleep(0.2)

        self.assertEqual(exec_interface.state, InterfaceState.SHUTDOWN)

    async def test_subprocess_shutdown(self):
        """ Can we shutdown the subprocess interface gracefully?
        """
        # Find out where the path to python might be
        exec_interface = await self.invoke_subprocess()

        await exec_interface.shutdown()

        self.assertEqual(exec_interface.state, InterfaceState.SHUTDOWN)

    async def test_subprocess_run_error(self):
        """ Checks if we can handle errors gracefully. """
        # Find out where the path to python might be
        invoke_command_path = pathlib.Path(sys.executable)
        exec_interface = await self.invoke_subprocess(
            exec_uri = f"exec:///{invoke_command_path}?arg=tests/scripts/error.py",
            expected_running=False,
            expected_state = InterfaceState.SHUTDOWN,
        )
        await asyncio.sleep(0.1)



# TODO: some way of capturing errors from the subprocess interface?
# TODO: separate channels for stderr and stdout?