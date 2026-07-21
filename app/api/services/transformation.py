from app.api.schemas.event import Operation


class Transformation:
    async def apply_operation(self, doc: list, op: Operation):
        text: list = list(op.text)
        if op.kind == "insert":
            """
            add from the beginning to the character before the position
            of insertion to the text to be inserted to the postion of
            insertion till the end of the list
            """
            return doc[: op.pos] + text + doc[op.pos :]
        else:
            """
            add from the beginning to the character before the text
            to be deleted and from the character after the text to be
            deleted till the end of the list
            """
            return doc[: op.pos] + doc[op.pos + len(text) :]

    async def transform_insertion_against_insertion(
        self, op1: Operation, op2: Operation
    ) -> int:
        if op2.pos < op1.pos:
            return op2.pos
        else:
            return op2.pos + len(op1.text)

    async def transform_insertion_against_deletion(
        self, op1: Operation, op2: Operation
    ) -> int:
        if op2.pos < op1.pos:
            return op2.pos
        else:
            return op2.pos + len(op1.text)

    async def transform_deletion_against_insertion(
        self, op1: Operation, op2: Operation
    ) -> int:
        if op1.pos >= op2.pos:
            return op2.pos
        elif op2.pos >= (op1.pos + len(op1.text)):
            return op2.pos - len(op1.text)
        else:
            return op1.pos  # insertion point was inside the deleted range

    async def transform_deletion_against_deletion(
        self, op1: Operation, op2: Operation
    ) -> int:
        if op1.pos > op2.pos:
            return op2.pos
        elif op1.pos < op2.pos:
            return op2.pos - len(op1.text)
        else:
            return

    async def transform(self, op1: Operation, op2: Operation):
        if op1.kind == "insert" and op2.kind == "insert":
            pos: int = await self.transform_insertion_against_insertion(op1, op2)
        elif op1.kind == "insert" and op2.kind == "delete":
            pos: int = await self.transform_insertion_against_deletion(op1, op2)
        elif op1.kind == "delete" and op2.kind == "insert":
            pos: int = await self.transform_deletion_against_insertion(op1, op2)
        elif op1.kind == "delete" and op2.kind == "delete":
            pos: int | None = await self.transform_deletion_against_deletion(op1, op2)
        return pos
