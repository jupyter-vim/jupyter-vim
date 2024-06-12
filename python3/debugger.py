import asyncio
import json

class DAPProxy():
    """Pass DAP messages from and to the Jupyter kernel."""
    def __init__(self, kernel_client):
        self.kernel_client = kernel_client
        self.kernel_tasks = dict()
        self.vimspector_task = None

    def start(self):
        asyncio.run_coroutine_threadsafe(self._start(), self.kernel_client.loop)

    def stop(self):
        self.kernel_client.loop.call_soon_threadsafe(self._stop)

    async def _start(self):
        server = await asyncio.start_server(self._accept_connection, port=9000)
        try:
            async with server:
                await server.serve_forever()
        except asyncio.CancelledError:
            pass

    def _stop(self):
        """Needs to be called inside the eventloop thread."""
        if len(self.kernel_tasks) > 0:
            for task in self.kernel_tasks.values():
                task.cancel()
            self.kernel_tasks = dict()
        if self.vimspector_task:
            self.vimspector_task.cancel()
            self.vimspector_task = None

    async def _accept_connection(self, reader, writer):
        self.kernel_client.thread_echom('Vimspector connected.',
                                        style='Question')
        self._writer = writer
        await asyncio.gather(self._listen_to_kernel('control', writer),
                             self._listen_to_kernel('iopub', writer),
                             self._listen_to_vimspector(reader))
        self.kernel_client.thread_echom('Vimspector disconnected.',
                                        style='Question')

    async def _listen_to_kernel(self, channel, writer):
        try:
            while not self.kernel_client.loop.is_closed():
                # Store the task so we can cancel() it if needed
                self.kernel_tasks[channel] = self.kernel_client.loop.create_task(
                    self.kernel_client.get_next_msg(channel)
                )
                msg = await self.kernel_tasks[channel]
                if msg['msg_type'].startswith('debug_'):
                    # if self.recording == 'initialize':
                    #     self.init_response.append(msg)
                    # elif self.recording == 'attach':
                    #     self.attach_response.append(msg)
                    await self._pass_to_vimspector(msg)
        except asyncio.CancelledError:
            # The task was cancelled, probably because the self._stop()
            # function was called.
            pass

    async def _pass_to_vimspector(self, msg):
        content = json.dumps(msg['content'])
        self._writer.write(
            f'Content-Length: {len(content)}\r\n\r\n{content}\r\n'.encode('utf8')
        )
        await self._writer.drain()

    async def _listen_to_vimspector(self, reader):
        try:
            while not self.kernel_client.loop.is_closed():
                # Store the task so we can cancel() it if needed
                self.vimspector_task = self.kernel_client.loop.create_task(
                    reader.readuntil(b'\r\n\r\n')
                )
                data = await self.vimspector_task
                data = data.decode('utf8').strip()
                header = dict()
                for line in data.split('\r\n'):
                    key, val = line.split(':')
                    key = key.lower()
                    if key == 'content-length':
                        val = int(val)
                    else:
                        val = val.strip()
                    header[key.strip()] = val

                # Read a body
                self.vimspector_task = self.kernel_client.loop.create_task(
                    reader.readexactly(header['content-length'])
                )
                data = await self.vimspector_task
                body = json.loads(data)

                # Pass the message along to the kernel
                msg = self.kernel_client.km_client.session.msg('debug_request', body)
                self.kernel_client.thread_send_msg('control', msg)
        except asyncio.CancelledError:
            pass
        except asyncio.exceptions.IncompleteReadError:
            # This happens when vimspector disconnects
            pass

        # Vimspector disconnected. Stop listening to the kernel.
        self._stop()
