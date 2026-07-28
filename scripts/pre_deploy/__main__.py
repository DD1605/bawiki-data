import asyncio
import importlib
import os

AUTO_RUN_SCRIPTS = [
    "gen_student_id_map",
    "update_emoji_list",
    "update_stu_alias_list",
    "update_wiki_stu_li",
]
OPTIONAL_SCRIPTS = {
    "gen_gacha_data": "BAWIKI_UPDATE_GACHA",
}


def get_script_names() -> list[str]:
    scripts = [*AUTO_RUN_SCRIPTS]
    scripts.extend(
        script
        for script, env_name in OPTIONAL_SCRIPTS.items()
        if os.getenv(env_name) == "1"
    )
    return scripts


async def run():
    tasks = [
        importlib.import_module(f".{script}", "scripts.pre_deploy").main()
        for script in get_script_names()
    ]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(run())
