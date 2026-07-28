import asyncio
import json
import time
from typing import List, cast

import anyio

from ..base.const import GACHA_JSON_PATH
from ..base.utils import schale_get, schale_get_stu_data

NORMAL_RATE = {"3": 3.0, "2": 18.5, "1": 78.5}
FES_RATE = {"3": 6.0, "2": 18.5, "1": 75.5}
UP_RATE = {"3": 0.7, "2": 3.0}
REGION_NAME_MAP = {
    "Jp": "日服",
    "Global": "国际服",
    "Cn": "国服",
}
DEFAULT_POOL_ORDER = ["Cn", "Global", "Jp"]
NORMAL_LIMITED_TYPE = 0
ARCHIVE_LIMITED_TYPE = 4
FES_LIMITED_TYPE = 3
FES_LIMITED_EXTRA_RATE = 0.9

BASE_DICT = {
    "3": {"chance": NORMAL_RATE["3"], "char": []},
    "2": {"chance": NORMAL_RATE["2"], "char": []},
    "1": {"chance": NORMAL_RATE["1"], "char": []},
}


def get_region_value(student: dict, key: str, region_index: int, default=0):
    values = student.get(key) or []
    if len(values) <= region_index:
        return default
    return values[region_index]


def is_released(student: dict, region_index: int) -> bool:
    return bool(get_region_value(student, "IsReleased", region_index, False))


def is_fes_limited(student: dict, region_index: int) -> bool:
    return get_region_value(student, "IsLimited", region_index) == FES_LIMITED_TYPE


def make_empty_base() -> dict:
    return {
        "3": {"chance": NORMAL_RATE["3"], "char": []},
        "2": {"chance": NORMAL_RATE["2"], "char": []},
        "1": {"chance": NORMAL_RATE["1"], "char": []},
    }


def build_base_pool(
    stu_li: List[dict],
    region_index: int,
    limited_type: int,
) -> dict:
    ret = make_empty_base()
    for student in stu_li:
        if not is_released(student, region_index):
            continue
        if get_region_value(student, "IsLimited", region_index) != limited_type:
            continue
        star = str(student["StarGrade"])
        if star in ret:
            ret[star]["char"].append(student["Id"])
    for value in ret.values():
        value["char"].sort()
    return ret


def build_archive_pool(stu_li: List[dict], region_index: int) -> dict:
    normal_pool = build_base_pool(stu_li, region_index, NORMAL_LIMITED_TYPE)
    archive_pool = build_base_pool(stu_li, region_index, ARCHIVE_LIMITED_TYPE)
    normal_pool["3"]["char"] = archive_pool["3"]["char"]
    return normal_pool


def get_released_fes_limited(stu_li: List[dict], region_index: int) -> List[dict]:
    return sorted(
        [
            x
            for x in stu_li
            if x["StarGrade"] == 3
            and is_fes_limited(x, region_index)
            and get_region_value(x, "IsReleased", region_index, False)
        ],
        key=lambda x: x["Id"],
    )


def pool_rate(rate: dict) -> dict:
    return {k: float(v) for k, v in rate.items()}


def up_rate(stars: List[int]) -> dict:
    return {
        str(star): UP_RATE[str(star)]
        for star in sorted(set(stars), reverse=True)
        if str(star) in UP_RATE
    }


async def main():
    # 获取学生数据，现在是字典格式而不是列表
    stu_dict = cast(dict, await schale_get_stu_data(raw=True))
    # 创建学生列表，方便后续处理
    stu_li = list(stu_dict.values())

    # region base
    for i in stu_li:
        s_id = i["Id"]
        s_name = i["Name"]
        star_grade = i["StarGrade"]
        print(
            f'gacha: {star_grade}星 {i.get("IsLimited", [])}：({s_id}) {s_name}',
        )

    base_pools = {
        region: build_base_pool(stu_li, index, NORMAL_LIMITED_TYPE)
        for index, region in enumerate(REGION_NAME_MAP)
    }
    archive_base_pools = {
        f"{region}Archive": build_archive_pool(stu_li, index)
        for index, region in enumerate(REGION_NAME_MAP)
    }
    base_pools.update(
        {
            key: value
            for key, value in archive_base_pools.items()
            if value["3"]["char"]
        },
    )

    # 旧插件兼容：默认 base 继续使用国服普通池。
    BASE_DICT["3"]["char"] = base_pools["Cn"]["3"]["char"]
    BASE_DICT["2"]["char"] = base_pools["Cn"]["2"]["char"]
    BASE_DICT["1"]["char"] = base_pools["Cn"]["1"]["char"]
    # endregion

    # region current_pools
    # 初始化卡池列表。限定/Fes 限定不会生成一个伪“限定池”，而是在具体当期池里
    # 通过 pool 或 extra_pools 表达。档案招募池使用 type=4 的老角色基础池。
    pools = [
        {
            "name": f"【{REGION_NAME_MAP[region]}】常驻池",
            "server": region,
            "base": region,
            "pool": [],
            "rate": pool_rate(NORMAL_RATE),
        }
        for region in DEFAULT_POOL_ORDER
    ]
    for region in ["Global", "Jp"]:
        archive_base = base_pools.get(f"{region}Archive")
        if archive_base and archive_base["3"]["char"]:
            pools.append(
                {
                    "name": f"【{REGION_NAME_MAP[region]}】档案招募",
                    "server": region,
                    "base": f"{region}Archive",
                    "pool": [],
                    "rate": pool_rate(NORMAL_RATE),
                },
            )

    common_data = cast(dict, await schale_get("data/config.min.json"))
    regions: List[dict] = common_data["Regions"]

    for region_index, region in enumerate(regions):
        region_key = region["Name"]
        region_name = REGION_NAME_MAP[region_key]
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
                rate = FES_RATE if is_fes_limited(up, region_index) else NORMAL_RATE
                pool = {
                    "name": f"【{region_name}】{name}",
                    "server": region_key,
                    "base": region_key,
                    "pool": ids,
                    "rate": pool_rate(rate),
                    "up_rate": up_rate([x["StarGrade"] for x in [up, *others]]),
                }

                if is_fes_limited(up, region_index):
                    extra_pool = [
                        x["Id"]
                        for x in get_released_fes_limited(stu_li, region_index)
                        if x["Id"] not in ids
                    ]
                    if extra_pool:
                        pool["extra_pools"] = [
                            {
                                "name": "Fes限定歪出",
                                "star": 3,
                                "chance": FES_LIMITED_EXTRA_RATE,
                                "pool": extra_pool,
                                "pickup": False,
                            }
                        ]

                pools.append(pool)

    print(f"gacha: 当期卡池：{json.dumps(pools, ensure_ascii=False, indent=2)}")
    # endregion

    j = json.loads(await anyio.Path(GACHA_JSON_PATH).read_text(encoding="u8"))
    j["base"] = BASE_DICT
    j["base_pools"] = base_pools
    j["rate"] = pool_rate(NORMAL_RATE)
    j["up_rate"] = pool_rate(UP_RATE)
    j["up"] = {star: {"chance": chance} for star, chance in UP_RATE.items()}
    j["current_pools"] = pools

    dump_j = json.dumps(j, indent=2, ensure_ascii=False)
    await anyio.Path(GACHA_JSON_PATH).write_text(dump_j, encoding="u8")

    print("gacha: complete")


if __name__ == "__main__":
    asyncio.run(main())
