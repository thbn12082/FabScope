import json


class GatewayError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


class Gateway:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def connected(flags):
        if flags["disconnected"]:
            raise GatewayError("DISCONNECTED", "Đường giao tiếp mô phỏng bị ngắt. Trạng thái khách đã cũ.")

    def command(self, command):
        def apply(engine, flags, db):
            self.connected(flags)
            result = self.store.command(command, engine, db)
            lose = flags["lost_ack_once"]
            if lose:
                flags["lost_ack_once"] = False
            return result, lose
        result, lost = self.store.transact(apply)
        # Raise only AFTER commit. The client cannot infer accepted/rejected from a 503.
        if lost:
            raise GatewayError("ACK_LOST", "Phản hồi bị mất sau khi lưu kết quả. Gửi lại nguyên command ID.")
        return result

    def state(self):
        def read(engine, flags, db):
            self.connected(flags)
            return engine.view()
        return self.store.transact(read)

    def events(self, after, limit):
        def read(engine, flags, db):
            self.connected(flags)
            items = [json.loads(r[0]) for r in db.execute(
                "SELECT data FROM events WHERE sequence>? ORDER BY sequence LIMIT ?", (after, limit))]
            cursor = items[-1]["sequence"] if items else after
            delivered = [e for item in items for e in ([item, item] if flags["duplicate_delivery"] else [item])]
            return dict(events=delivered, next_cursor=cursor, has_more=cursor < engine.state["sequence"],
                        journal_sequence=engine.state["sequence"], simulation_notice=self.store.config["simulation_notice"])
        return self.store.transact(read)
