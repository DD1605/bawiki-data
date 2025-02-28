import asyncio
import json
import time
from typing import List, cast

import anyio

from ..base.const import GACHA_JSON_PATH
from ..base.utils import schale_get, schale_get_stu_data

BASE_DICT = {
    "3": {"chance": 2.5, "char": []},
    "2": {"chance": 18.5, "char": []},
    "1": {"chance": 79.0, "char": []},
}


async def main():
    # 获取学生数据，现在是字典格式而不是列表
    stu_dict = cast(dict, await schale_get_stu_data(raw=True))
    # 创建学生列表，方便后续处理
    stu_li = list(stu_dict.values())

    # region base
    star3 = []
    star2 = []
    star1 = []
    
    # 存储所有常驻角色的ID
    permanent_pool = []
    # 限定池角色ID列表
    limited_pool = []

    for i in stu_li:
        s_id = i["Id"]
        s_name = i["Name"]
        star_grade = i["StarGrade"]
        # 检查是否存在 IsLimited 字段，如果不存在默认为 0
        limited = i.get("IsLimited", 0)
        if not limited:
            if star_grade == 3:
                star3.append(s_id)
            elif star_grade == 2:
                star2.append(s_id)
            elif star_grade == 1:
                star1.append(s_id)
            
            # 将限定角色添加到限定池
        else:
            limited_pool.append(s_id)
            

        print(
            f'gacha: {star_grade}星{"[限定]" if limited else " 常驻 "}：({s_id}) {s_name}',
        )

    star3.sort()
    star2.sort()
    star1.sort()
    limited_pool.sort()

    BASE_DICT["3"]["char"] = star3
    BASE_DICT["2"]["char"] = star2
    BASE_DICT["1"]["char"] = star1
    # endregion

    # region current_pools
    region_name_map = {
        "Jp": "日服",
        "Global": "国际服",
        "Cn": "国服",
    }

    # 初始化卡池列表，添加常驻池和限定池
    pools = [
        {
            "name": "常驻池",
            "pool": permanent_pool
        },
        {
            "name": "限定池",
            "pool": limited_pool
        }
    ]

    common_data = cast(dict, await schale_get("data/config.min.json"))
    regions: List[dict] = common_data["Regions"]

    for region in regions:
        region_name = region_name_map[region["Name"]]
        gachas = region["CurrentGacha"]
        for gacha in gachas:
            if not (gacha["start"] <= time.time() < gacha["end"]):
                continue

            characters = gacha["characters"]
            # 使用新的字典结构获取角色数据
            three_star: List[dict] = [
                stu_dict[str(x)] for x in characters if stu_dict[str(x)]["StarGrade"] == 3
            ]
            three_star_ids = [x["Id"] for x in three_star]
            others: List[dict] = [
                stu_dict[str(x)] for x in characters if x not in three_star_ids
            ]

            for up in three_star:
                name = "、".join((up["Name"], *(x["Name"] for x in others)))
                ids = [up["Id"], *(x["Id"] for x in others)]
                pools.append({"name": f"【{region_name}】{name}", "pool": ids})

    print(f"gacha: 当期卡池：{json.dumps(pools, ensure_ascii=False, indent=2)}")
    # endregion

    j = json.loads(await anyio.Path(GACHA_JSON_PATH).read_text(encoding="u8"))
    j["base"] = BASE_DICT
    j["current_pools"] = pools

    dump_j = json.dumps(j, indent=2, ensure_ascii=False)
    await anyio.Path(GACHA_JSON_PATH).write_text(dump_j, encoding="u8")

    print("gacha: complete")


if __name__ == "__main__":
    asyncio.run(main())