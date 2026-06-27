from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

REPORT_TEMPLATE = (
    "【自动报告】：@{mascot_name}\n"
    "【妹子花名】：#{mascot_name}\n"
    "【修车类型】：一课，两课，双飞，包夜；\n"
    "【身高身材】：目测身高、身材形容（苗条、过瘦、偏胖等等）；\n"
    "【颜值相似】：真人和照片几分像；\n"
    "【凶器罩杯】：目测凶器大小，A-H；\n"
    "【服务项目】：实际过程中包含的所有服务项目（尽量不要遗漏）；\n"
    "【服务详情】：具体写整个服务过程、感受等（尤其特点）自由发挥；\n"
    "【机车行为】：是否有机车行为（久等、态度差、玩手机、催等等）；\n"
    "【优点缺点】：简短总结优缺点；\n"
    "【调教建议】：请指出一些可以优化的细节；\n"
    "【推荐程度】：X.X分/满分10.0分；"
)


def get_report_kb(report_id, likes=0, dislikes=0):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"👍 {likes}", callback_data=f"vote_like_{report_id}"),
        InlineKeyboardButton(f"👎 {dislikes}", callback_data=f"vote_dislike_{report_id}"),
    )
    return kb
