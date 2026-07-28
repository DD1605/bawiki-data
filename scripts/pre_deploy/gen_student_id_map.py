import asyncio
import json
from typing import cast

import anyio

from ..base.const import STUDENT_ID_MAP_JSON_PATH
from ..base.utils import schale_get_stu_data


async def main():
    stu_dict = cast(dict, await schale_get_stu_data(raw=True))
    student_id_map = {
        str(student["Id"]): {
            "name": student["Name"],
            "star": student["StarGrade"],
            "path": student.get("PathName", ""),
            "is_limited": student.get("IsLimited", []),
            "is_released": student.get("IsReleased", []),
        }
        for student in sorted(stu_dict.values(), key=lambda x: x["Id"])
    }

    await anyio.Path(STUDENT_ID_MAP_JSON_PATH).write_text(
        json.dumps(student_id_map, indent=2, ensure_ascii=False),
        encoding="u8",
    )

    print("student_id_map: complete")


if __name__ == "__main__":
    asyncio.run(main())
