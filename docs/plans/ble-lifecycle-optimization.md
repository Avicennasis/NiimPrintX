# BLE start_notify/stop_notify Lifecycle Optimization

**Status:** Plan (not yet implemented)
**TODO ref:** "Performance: BLE start_notify/stop_notify lifecycle"
**Date:** 2026-04-12

---

## 1. Current Behavior Analysis

### How send_command works today

Every call to `PrinterClient.send_command()` (printer.py:111-157) follows this sequence:

1. Acquire `_command_lock`
2. Clear stale notification state (`notification_event`, `notification_data`)
3. Call `transport.start_notification(char_uuid, handler)` -- arms BLE notifications
4. Write the command packet
5. Wait for the notification response (with timeout)
6. In `finally`: call `transport.stop_notification(char_uuid)` -- tears down BLE notifications

`BLETransport.start_notification()` (bluetooth.py:95-104) has an existing optimization: it tracks `_notifying_uuids` and skips the actual `client.start_notify()` BLE call if the UUID is already subscribed. However, `stop_notification()` (bluetooth.py:106-111) unconditionally tears down the subscription and removes the UUID from the tracking set.

This means the `start_notification` optimization is never effective because `stop_notification` is called after every single command, forcing the next `start_notification` to re-arm from scratch.

### Actual call counts per print job

A typical `_print_job()` (printer.py:204-285) makes these `send_command` calls:

| Step | Method | send_command calls |
|------|--------|--------------------|
| 1 | `set_label_density()` | 1 |
| 2 | `set_label_type()` | 1 |
| 3 | `start_print()` or `start_print_v2()` | 1 |
| 4 | `start_page_print()` | 1 |
| 5 | `set_dimension()` or `set_dimension_v2()` | 1 |
| 6 | `set_quantity()` (v1 only) | 0 or 1 |
| 7 | Image row writes via `write_raw()` | 0 (does NOT use send_command) |
| 8 | `end_page_print()` polling (up to 200 tries) | 1-200 |
| 9 | `get_print_status()` polling (up to 600 tries) | 1-600 |
| 10 | `end_print()` | 1 |

**Typical case:** ~10-15 send_command calls (steps 1-6 + a few end_page polls + a few status polls + end_print).

**Worst case:** ~807 send_command calls (steps 1-6 at 6 + 200 end_page polls + 600 status polls + 1 end_print).

The TODO's "800 BLE round-trips" figure refers to the theoretical worst case of polling loops, not the image row writes (which use `write_raw` and bypass send_command entirely).

### BLE round-trip cost

Each unnecessary stop_notify/start_notify cycle is 2 BLE GATT operations. At the BLE stack level:
- `stop_notify` writes a Client Characteristic Configuration Descriptor (CCCD) value of `0x0000`
- `start_notify` writes a CCCD value of `0x0001`

Each GATT write involves at minimum one BLE connection interval (~7.5ms-4s depending on negotiated parameters, typically ~30-50ms on these printers). So each wasted cycle costs ~60-100ms of real wall-clock time.

**Typical print job waste:** 10-15 cycles * ~80ms = ~0.8-1.2s
**Worst-case print job waste:** ~800 cycles * ~80ms = ~64s

The status polling loop is where this really hurts -- each poll does stop+start+write+wait+stop, when it could just do write+wait.

### Outside print jobs

The CLI `info` command (command.py:201-222) calls `get_info()` three times in sequence. Each call triggers a full start/stop cycle. The UI heartbeat loop calls `heartbeat()` repeatedly with ~1s intervals. These are lower priority but would also benefit.

---

## 2. Proposed Changes

Hold the BLE notification subscription open for the duration of a logical operation (print job, info query sequence, heartbeat loop) rather than tearing it down after every individual command. The `_command_lock` already serializes `send_command` calls, so there is no risk of concurrent notification confusion.

---

## 3. Design Options

### Option A: Notification Session Context Manager

Add an async context manager to `PrinterClient` that holds the notification subscription open. Callers wrap their sequences of commands in a `with` block:

```python
class PrinterClient:
    @contextlib.asynccontextmanager
    async def notification_session(self):
        """Hold BLE notification subscription open for multiple commands."""
        if self.char_uuid is None:
            raise PrinterException("No characteristic UUID available")
        await self.transport.start_notification(self.char_uuid, self.notification_handler)
        self._in_session = True
        try:
            yield
        finally:
            self._in_session = False
            try:
                await self.transport.stop_notification(self.char_uuid)
            except Exception as e:
                logger.warning(f"stop_notify failed: {e}")

    async def send_command(self, ...):
        async with self._command_lock:
            notifying = False
            try:
                ...
                if not self._in_session:
                    await self.transport.start_notification(char_uuid, self.notification_handler)
                    notifying = True
                ...
            finally:
                if notifying and not self._in_session and char_uuid is not None:
                    await self.transport.stop_notification(char_uuid)
```

Usage in `_print_job`:
```python
async with self.notification_session():
    await self.set_label_density(density)
    await self.set_label_type(1)
    ...
```

**Pros:**
- Explicit, visible scope for the subscription lifetime
- Backward compatible -- standalone `send_command` calls (outside a session) still self-manage
- Easy to add to CLI `_info()` and heartbeat loop as well
- Clear cleanup semantics

**Cons:**
- Requires modifying every call site that wants the optimization (_print_job, CLI _info, heartbeat loop)
- Slight complexity: `_in_session` flag adds a state variable
- The `notification_session` must be acquired outside `_print_lock` or inside it, creating ordering questions

### Option B: Remove stop_notify from send_command; Stop Only on Disconnect

Never tear down the notification subscription after individual commands. Start it on the first `send_command` and leave it armed until `disconnect()` is called.

```python
async def send_command(self, ...):
    async with self._command_lock:
        try:
            ...
            await self.transport.start_notification(char_uuid, self.notification_handler)
            # start_notification is already idempotent -- no-ops if already armed
            ...
        finally:
            # NO stop_notification here
            self.notification_event.clear()

async def disconnect(self):
    if self.char_uuid:
        with contextlib.suppress(Exception):
            await self.transport.stop_notification(self.char_uuid)
    self.char_uuid = None
    await self.transport.disconnect()
```

**Pros:**
- Simplest change -- remove lines from `send_command`, add one block to `disconnect`
- Zero call site changes needed
- `start_notification` idempotency (already implemented) means the start call becomes a no-op after the first command
- Notification handler already guards against stale data via `notification_event.clear()` at the top of `send_command`

**Cons:**
- Notifications stay armed for the entire connection lifetime, even during idle periods
- If the printer sends unsolicited notifications (the separate TODO item), they would arrive at the handler while no command is in flight; the current handler would set `notification_data` and `notification_event`, potentially causing a subsequent `send_command` to read stale data -- BUT the existing code already clears both at the top of `send_command` before writing, so this is mitigated
- Some BLE stacks (especially on macOS/Windows) have been observed to have issues with long-lived notification subscriptions and idle connections, though this is uncommon with modern bleak
- Violates the principle of acquiring resources for the minimum time needed

### Option C: Reference Counting on start/stop

Track a reference count in `BLETransport`. Each `start_notification` increments; each `stop_notification` decrements. Only actually call `client.stop_notify` when the count hits zero.

```python
class BLETransport:
    def __init__(self):
        self._notify_refcount: dict[str, int] = {}

    async def start_notification(self, char_uuid, handler):
        if char_uuid in self._notify_refcount:
            self._notify_refcount[char_uuid] += 1
            return  # already armed
        self._notify_refcount[char_uuid] = 1
        await self.client.start_notify(char_uuid, handler)

    async def stop_notification(self, char_uuid):
        count = self._notify_refcount.get(char_uuid, 0)
        if count > 1:
            self._notify_refcount[char_uuid] = count - 1
            return  # still in use
        # Actually stop
        del self._notify_refcount[char_uuid]
        await self.client.stop_notify(char_uuid)
```

**Pros:**
- No changes to `send_command` or `_print_job` at all
- A session context manager can simply call start/stop once, and the refcount holds it open
- Clean abstraction at the transport layer

**Cons:**
- Reference counting is notoriously error-prone -- missed decrements leak subscriptions, double decrements cause premature teardown
- Does not actually solve the problem on its own -- `send_command` still calls stop in its finally, which would decrement to zero unless something else holds a reference. So this still needs a session wrapper or similar to be useful.
- Adds complexity to the transport layer for a problem that is better solved at the application layer
- The existing `_notifying_uuids` set is simpler and already covers the "is it armed?" check

---

## 4. Recommended Approach: Option B (Stop Only on Disconnect)

**Option B is the best choice** for the following reasons:

1. **Simplest change with highest impact.** It requires modifying only two methods: `send_command` (remove the stop_notification call from finally) and `disconnect` (add stop_notification before disconnect). Zero call sites need updating.

2. **The existing code already handles the main risk.** The concern with long-lived subscriptions is stale notification data. But `send_command` already clears `notification_event` and `notification_data` at lines 122-123, BEFORE arming notifications and writing. This means any unsolicited notification that arrived during idle time is discarded.

3. **`start_notification` idempotency is already implemented.** After the first `send_command` arms notifications, all subsequent calls become no-ops at the transport layer (bluetooth.py:98 check). This eliminates both the start AND stop overhead for every command after the first.

4. **The `_command_lock` serializes everything.** There is no risk of concurrent commands interfering with each other's notification state. Only one command is ever in-flight at a time.

5. **Real-world usage pattern supports it.** The printer connection is short-lived: connect -> print -> disconnect (CLI) or connect -> heartbeat loop + occasional print -> disconnect (UI). There is no scenario where the connection is held idle for hours with notifications armed.

6. **BLE stack compatibility.** Modern bleak (which this project uses) handles long-lived notification subscriptions reliably across platforms. The BLE spec explicitly supports persistent notification subscriptions -- it is the normal mode of operation for most BLE peripherals.

### Enhancement: Defensive Clear in notification_handler

As a safety measure against the unsolicited notification concern, add a guard so `notification_handler` only processes data when a command is actually waiting. This is not strictly necessary for Option B but hardens the design:

```python
def notification_handler(self, sender, data):
    if self._loop is None:
        return
    def _set():
        if not self.notification_event.is_set():
            self.notification_data = bytes(data)
            self.notification_event.set()
    self._loop.call_soon_threadsafe(_set)
```

This handler already has the `if not self.notification_event.is_set()` guard (printer.py:178), which means only the first notification after `notification_event.clear()` is accepted. Combined with the clear at the top of `send_command`, this is sufficient.

---

## 5. File Changes

### 5.1 `NiimPrintX/nimmy/printer.py`

**send_command() -- remove stop_notification from finally block:**

Current (lines 151-157):
```python
finally:
    if notifying and char_uuid is not None:
        try:
            await self.transport.stop_notification(char_uuid)
        except Exception as e:
            logger.warning(f"stop_notify failed: {e}")
    self.notification_event.clear()
```

Proposed:
```python
finally:
    self.notification_event.clear()
```

The `notifying` local variable and `char_uuid` snapshot (line 113-114) are no longer needed for the finally block, but `char_uuid` is still used earlier in the try body. The `notifying` variable can be removed entirely.

**disconnect() -- add stop_notification before transport.disconnect():**

Current (lines 82-86):
```python
async def disconnect(self) -> None:
    self.char_uuid = None
    await self.transport.disconnect()
    logger.info(f"Printer {self.device.name!r} disconnected.")
```

Proposed:
```python
async def disconnect(self) -> None:
    if self.char_uuid is not None:
        with contextlib.suppress(Exception):
            await self.transport.stop_notification(self.char_uuid)
    self.char_uuid = None
    await self.transport.disconnect()
    logger.info(f"Printer {self.device.name!r} disconnected.")
```

Note: `contextlib` is already imported at the top of the file (line 5).

**Optional cleanup:** Remove the `notifying` variable from `send_command` since it is no longer used in the finally block. The `start_notification` call no longer needs a success flag.

### 5.2 `NiimPrintX/nimmy/bluetooth.py`

**No changes required.** The existing `start_notification` idempotency and `stop_notification` cleanup logic work correctly with this approach. `disconnect()` already calls `self._notifying_uuids.clear()` (line 82), so even if `stop_notification` is skipped, the tracking set is cleaned up.

### 5.3 `tests/conftest.py`

**Update make_client fixture:** The fixture currently mocks `stop_notification`. Many tests assert on `stop_notification` being called after each `send_command`. After this change, `stop_notification` should NOT be called after `send_command`, so existing assertions need updating.

No changes to the fixture itself, but the mock must remain available for `disconnect()` tests.

### 5.4 `tests/test_printer.py`

**Update tests that assert stop_notification is called after send_command.** These tests will need to verify that stop_notification is NOT called after individual commands, and IS called during disconnect.

Key tests to update:
- `test_send_command_stop_notification_failure_suppressed` (test_printer_uncovered.py:182) -- this test verifies that stop_notification errors are suppressed. It becomes obsolete because stop_notification is no longer called per-command. Replace with a test that verifies disconnect calls stop_notification and suppresses errors.
- Any test asserting `stop_notification.assert_awaited_once()` after a `send_command` call.
- `test_send_command_start_notification_failure_skips_stop` (test_coverage_gaps.py:153) -- the skip-stop logic changes; if start_notification fails, there is nothing to stop (still correct, but the `notifying` flag path is removed).

### 5.5 `tests/test_printer_uncovered.py`

**Update or replace** `test_send_command_stop_notification_failure_suppressed` as described above.

### 5.6 `tests/test_coverage_gaps.py`

**Update** `test_send_command_start_notification_failure_skips_stop` to reflect the removal of per-command stop_notification.

### 5.7 `tests/test_printer_reconnect.py`

**Review** `test_start_notification_idempotent` -- this test validates the transport-layer optimization and should still pass unchanged. But add a NEW integration-style test verifying that multiple `send_command` calls result in only one `start_notify` BLE call and zero `stop_notify` calls between commands.

### 5.8 New test: Lifecycle integration test

Add a test that simulates a print-job-like sequence:
1. Call `send_command` 5 times
2. Verify `start_notification` was called exactly once (first command arms, rest are no-ops)
3. Verify `stop_notification` was never called
4. Call `disconnect()`
5. Verify `stop_notification` was called exactly once

---

## 6. Risk Assessment

### 6.1 Unsolicited BLE notifications (HIGH -- mitigated)

**Risk:** If the printer sends notifications without being asked (e.g., status change, error condition), the `notification_handler` would set `notification_data` and `notification_event` at an unexpected time.

**Mitigation:** The existing handler already guards with `if not self.notification_event.is_set()` (printer.py:178). And `send_command` clears both state variables BEFORE writing the command (lines 122-123). An unsolicited notification arriving between `notification_event.clear()` and the actual write would be consumed, but this is a pre-existing race condition unrelated to this change.

**Interaction with TODO:** The "BLE unsolicited notification handling" TODO item would add proper handling for unsolicited notifications (e.g., a queue or separate callback). That work is complementary to this change and does not block it.

### 6.2 Connection drops during long-lived subscription (MEDIUM -- mitigated)

**Risk:** If the BLE connection drops while notifications are armed, the next `send_command` might fail on the write rather than the start_notification.

**Mitigation:** `send_command` already checks connection state at line 116 (`if not self.transport.client or not self.transport.client.is_connected`) and reconnects if needed. After reconnection, `_notifying_uuids` is cleared by `BLETransport.connect()` (bluetooth.py:65), so `start_notification` will re-arm correctly. No change in behavior.

### 6.3 BLE stack resource leak (LOW)

**Risk:** Some BLE stacks might leak resources if notifications are left armed for extended periods without stop/start cycling.

**Mitigation:** The connection lifetime is short (seconds to minutes for a print job). `disconnect()` now explicitly calls `stop_notification` before `transport.disconnect()`, ensuring clean teardown. This is actually MORE correct than the current code, where `disconnect()` does not call `stop_notification` at all -- it relies on the transport's `disconnect()` to implicitly clean up.

### 6.4 Handler callback reference after disconnect (LOW)

**Risk:** If the BLE stack delivers a notification callback after `disconnect()` has been called but before the stack fully shuts down, `notification_handler` could be invoked on a stale object.

**Mitigation:** The handler checks `self._loop is None` (printer.py:173). `disconnect()` does not currently clear `_loop`, but the `call_soon_threadsafe` call would fail gracefully if the loop is closed. This is a pre-existing condition.

### 6.5 Test brittleness (LOW)

**Risk:** Changing stop_notification behavior will break tests that assert on per-command stop_notification calls.

**Mitigation:** This is expected and the test changes are enumerated in section 5. The test updates are straightforward assertion changes, not architectural rework.

---

## 7. Testing Strategy

All testing can be done without BLE hardware using the existing mock infrastructure.

### 7.1 Unit tests (modify existing)

1. **send_command no longer calls stop_notification:** Mock transport, call `send_command`, assert `stop_notification.assert_not_awaited()`.

2. **disconnect calls stop_notification:** Mock transport, call `disconnect()`, assert `stop_notification.assert_awaited_once_with(char_uuid)`.

3. **disconnect with no char_uuid skips stop:** Set `char_uuid = None`, call `disconnect()`, assert `stop_notification.assert_not_awaited()`.

4. **disconnect suppresses stop_notification errors:** Set `stop_notification` side_effect to RuntimeError, call `disconnect()`, verify no exception raised.

5. **start_notification still called on first send_command:** Mock transport, call `send_command`, assert `start_notification.assert_awaited_once()`.

6. **start_notification idempotent across multiple send_commands:** This requires either making the mock stateful (tracking `_notifying_uuids`) or testing at the transport layer. The existing `test_start_notification_idempotent` covers the transport layer. Add a printer-layer test that calls `send_command` twice and verifies transport.start_notification was called twice (since the mock doesn't track state) but the actual BLE call would only happen once.

### 7.2 Integration-style tests (new)

1. **Print job lifecycle:** Simulate `_print_job` flow with mocked transport. Verify:
   - `start_notification` called on first `send_command`
   - `stop_notification` never called during the print job
   - After `disconnect()`, `stop_notification` called once

2. **Sequential print jobs:** Call `_print_job` twice (simulating reuse). Verify notification lifecycle is correct across both jobs.

3. **Error during print with disconnect:** Simulate `send_command` failure mid-print. Verify `_print_job`'s except handler calls `end_print`, and eventual `disconnect()` cleans up notifications.

### 7.3 Manual BLE testing (optional, requires hardware)

If hardware is available, verify:
- Print a label and confirm no regression in print quality or timing
- Check debug logs to confirm `start_notify` is called once and `stop_notify` only on disconnect
- Measure wall-clock time improvement on a label with many status polls

---

## 8. Blocked Items and Dependencies

### 8.1 BLE unsolicited notification handling (separate TODO)

The unsolicited notification TODO item is directly related but NOT blocked by this change. With the current approach (Option B), unsolicited notifications during idle periods would be received by `notification_handler`, but the existing guard (`if not self.notification_event.is_set()`) prevents them from corrupting state between commands. The `notification_event.clear()` at the top of each `send_command` provides the reset.

However, if the unsolicited notification work later introduces a separate callback or queue for out-of-band notifications, it would need to coexist with the long-lived subscription. The design should:
- Keep a single `start_notification` with the existing handler
- Add discrimination logic in `notification_handler` to route responses vs. unsolicited data
- This is additive and does not conflict with Option B

### 8.2 Reconnection logic

The reconnection path in `send_command` (line 116) calls `self.connect()`, which calls `transport.connect()`, which clears `_notifying_uuids` (bluetooth.py:65). This means after a reconnection, `start_notification` will correctly re-arm. No blocking issue.

### 8.3 UI heartbeat loop interaction

The UI heartbeat loop (PrintOption.py:51-73) calls `heartbeat()` every ~1s while connected. With Option B, the first heartbeat arms notifications and all subsequent heartbeats skip both start and stop. If a print job starts while the heartbeat is active, the `_command_lock` serializes access and the notification subscription stays armed. This is correct behavior with no blocking issue. However, `_print_lock` prevents print jobs from overlapping with each other, but does NOT prevent heartbeat calls from interleaving with print commands -- both use `_command_lock` for serialization, which is sufficient.

---

## Appendix: Estimated Performance Impact

| Scenario | Current overhead | After change | Savings |
|----------|-----------------|-------------|---------|
| Typical print (15 commands) | ~30 BLE ops (15 stop + 15 start) minus first start = 29 wasted | 0 wasted BLE ops | ~2.3s |
| Heavy polling print (200 end_page + 100 status) | ~600 wasted BLE ops | 0 wasted BLE ops | ~48s |
| CLI info (3 commands) | ~5 wasted BLE ops | 0 wasted BLE ops | ~0.4s |
| Single heartbeat | 1 wasted BLE op (stop) | 0 wasted BLE ops | ~0.05s |
| 60s of heartbeats (~60 calls) | ~119 wasted BLE ops | 0 wasted BLE ops | ~9.5s |

Note: Actual BLE timing varies with connection interval, stack implementation, and OS. The ~80ms per operation estimate is conservative. On some platforms (especially macOS CoreBluetooth), GATT operations can take 100-200ms each.
