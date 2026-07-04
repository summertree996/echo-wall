from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import ActionLog, AiSummaryCache, AuthEvent, Card, Reaction, ResearchEvent, User, Wall


DEMO_USERS = [
    ("demo@talon.wall", "崔晓琳", True),
    ("student@talon.wall", "赵欣", False),
    ("wang.meili@talon.wall", "王美丽", False),
    ("liu.zhenyu@talon.wall", "刘振宇", False),
    ("chen.yiran@talon.wall", "陈一然", False),
    ("sun.haoran@talon.wall", "孙浩然", False),
    ("lin.qi@talon.wall", "林琪", False),
    ("zhou.ming@talon.wall", "周铭", False),
    ("he.yu@talon.wall", "何雨", False),
]


SEED_CARDS = [
    ("赵欣", "positive", "点赞这次新上的反馈墙，想法能马上被大家看到，讨论氛围比传统问卷自然很多。", ["体验", "实时"]),
    ("王美丽", "negative", "如果匿名模式切换不够清楚，大家可能会担心身份暴露。建议主持人进入前先说明当前状态。", ["匿名", "信任"]),
    ("刘振宇", "neutral", "智能整理能不能保留原始卡片位置的入口？归类后最好还能跳回现场语境。", ["AI整理", "语境"]),
    ("崔晓琳", "positive", "主题岛屿这个视图很适合会后复盘，能快速看到哪些问题是共识，哪些只是个别意见。", ["主题聚类", "复盘"]),
    ("陈一然", "positive", "实时同步的存在感很强，两边屏幕一起变化时，能让参与者感觉自己确实在共同完成一面墙。", ["实时", "参与感"]),
    ("孙浩然", "neutral", "我会希望发布前能看到大概会贴在哪里，哪怕只是半透明轮廓，也比直接弹窗更有掌控感。", ["放置", "预览"]),
    ("林琪", "negative", "如果热门内容太抢眼，容易把晚到同学的细小问题盖住，最好把热门入口做得克制一些。", ["注意力", "公平"]),
    ("周铭", "positive", "Spotlight 很适合主持人带大家讨论某一张代表卡，投影出来比口头复述更直观。", ["Spotlight", "主持"]),
    ("何雨", "neutral", "整理视图最好明确告诉大家它只是临时排列，不然有人会误以为自己原来贴的位置被系统改掉了。", ["整理视图", "坐标"]),
    ("赵欣", "positive", "富文本不用复杂，但加粗和列表够用了。大家写反馈时能稍微组织一下重点，读起来会清楚很多。", ["富文本", "可读性"]),
    ("王美丽", "negative", "如果一进来只有管理员摘要，普通同学可能会觉得自己的表达被系统提前归类了，自由墙应该先出现。", ["自由墙", "表达"]),
    ("刘振宇", "positive", "AI 摘要带代表卡片证据这个点很重要，老师可以从总结直接回到原话，不会只看到空泛判断。", ["AI摘要", "证据"]),
    ("陈一然", "neutral", "口令墙可以保留，但不要做成复杂权限系统。课程反馈和食堂反馈用不同链接隔开就够清楚。", ["权限", "多墙"]),
    ("孙浩然", "positive", "左侧在线头像让现场有活人感，匿名模式打开后统一成匿名头像也能说明设计考虑过研究伦理。", ["在线", "匿名"]),
    ("林琪", "negative", "拖动时如果每一帧都写数据库会让人担心压力，松手后再保存这个解释更容易被技术面试官接受。", ["拖拽", "性能"]),
    ("周铭", "positive", "数据导出对科研场景很加分，评论、反应、时间线都能作为后续分析材料。", ["导出", "科研"]),
    ("何雨", "neutral", "我关心刷新后会不会丢状态。只要卡片位置、反应和 AI 标签都还在，就能说明后端真的入库了。", ["持久化", "后端"]),
    ("赵欣", "positive", "新增卡片发布后自动滚到自己那张并高亮，这个细节很舒服，用户不会觉得内容被系统扔丢了。", ["反馈", "高亮"]),
    ("王美丽", "negative", "如果画布过满，系统把卡片吸附到很远的位置时要提示原因，否则用户会以为点击不准。", ["吸附", "反馈"]),
    ("刘振宇", "positive", "演示模式可以在答辩或汇报时直接轮播 top 卡片，不需要临时截图做 PPT。", ["演示", "大屏"]),
    ("陈一然", "neutral", "主题标签可以先轻量展示，不一定一开始就做复杂的二级聚类，稳定性更重要。", ["主题", "取舍"]),
    ("孙浩然", "positive", "卡片略微歪一点、颜色不完全一致，比整齐网格更像真实便利贴墙。", ["视觉", "贴纸感"]),
    ("林琪", "negative", "如果普通用户也能打开后台式整理视图，体验会有点割裂，最好把它留给主持人。", ["角色", "整理视图"]),
    ("周铭", "positive", "多墙管理很适合展示完整产品思路，但普通参与者从链接直达就好，不需要给他们墙列表首页。", ["多墙", "入口"]),
    ("何雨", "neutral", "AI 失败时卡片也应该照常发布，标签晚一点出现或者没有标签都能接受。", ["AI", "鲁棒性"]),
    ("赵欣", "positive", "反应不只是点赞，想追问和有启发也很适合课堂场景，能把轻互动做得更丰富。", ["反应", "课堂"]),
    ("王美丽", "neutral", "我希望管理员能看到哪些意见有风险，但这个入口别压过原始墙面。", ["风险", "管理员"]),
    ("刘振宇", "positive", "单机单 worker 的部署解释如果写清楚，其实很适合面试项目，省掉 Redis 之后可交付性更强。", ["部署", "WebSocket"]),
    ("陈一然", "negative", "如果卡片重叠太多，滚轮或 hover 抬起要足够明显，不然会看不清下面的内容。", ["重叠", "可读性"]),
    ("孙浩然", "positive", "整体方向我喜欢：普通用户只感到自己在贴纸，管理员需要时再进入整理和摘要。", ["产品", "分层"]),
]

REACTION_PATTERN = [7, 4, 5, 8, 6, 3, 4, 7, 3, 5, 4, 8, 3, 6, 5]
REACTION_TYPES = ["like", "dislike", "question"]
DEMO_WALL_ID = "w_demo_open_feedback"
COURSE_WALL_ID = "w_demo_course_week4"
CANTEEN_WALL_ID = "w_demo_canteen_feedback"
DEMO_WALL_IDS = [DEMO_WALL_ID, COURSE_WALL_ID, CANTEEN_WALL_ID]

# Coordinates are card centers. The main demo wall is tuned as a curated stage:
# the first viewport keeps complete cards inside a 1280px working width, leaves
# a clear lower breathing area for live posting, and avoids relying on horizontal
# scrolling during the interview walkthrough.
DEMO_OPEN_LAYOUT_POINTS = [
    (285, 235), (535, 205), (805, 235), (1045, 210),
    (320, 485), (575, 455), (835, 500), (1060, 470),
    (1000, 770), (1040, 805), (975, 835), (420, 1230),
    (760, 1265), (1020, 1340), (250, 1470), (610, 1535),
    (930, 1620), (360, 1750), (760, 1830), (1020, 1910),
    (500, 2080), (875, 2160), (245, 2325), (650, 2405),
    (1010, 2500), (400, 2650), (780, 2730), (1020, 2850),
    (300, 3020), (660, 3110), (1000, 3210), (500, 3370),
    (860, 3490),
]

SECONDARY_LAYOUT_POINTS = [
    (590, 190), (345, 275), (845, 285), (620, 455),
    (1070, 475), (470, 650), (755, 720), (250, 880),
    (1015, 965), (585, 1085), (330, 1215), (795, 1310),
]

COLOR_SEQUENCE = [
    "yellow", "blue", "pink", "green", "beige", "purple",
    "yellow", "green", "pink", "blue", "beige", "purple",
    "green", "yellow", "blue", "pink", "beige", "green",
    "purple", "yellow", "blue", "pink", "green", "beige",
    "purple", "yellow", "blue", "pink", "green", "beige",
]

ROTATION_SEQUENCE = [
    -1.6, 1.2, -0.9, 1.8, 0.7, -2.0, 1.4, -1.1, 2.8, -2.2,
    1.6, -2.1, 0.2, 1.5, -0.8, 3.2, -1.0, 0.5, -2.5, 1.0,
    -0.4, 2.0, -1.1, 0.7, -3.1, 1.4, -1.6, 0.3, 2.3, -3.4,
]

DEMO_ACTIVITY_START = datetime(2026, 7, 4, 9, 18, 0)

COURSE_CARDS = [
    ("赵欣", "positive", "本周案例讨论很有效，老师把研究设计和真实访谈材料连在一起讲，之前抽象的方法概念变清楚了。", ["课程", "案例"]),
    ("王美丽", "neutral", "希望下次课前能提前一天发阅读清单，大家可以带着问题来，课堂讨论会更集中。", ["预习", "节奏"]),
    ("刘振宇", "negative", "小组展示时间有点紧，后两组明显被压缩，建议每组固定留出回应问题的时间。", ["展示", "公平"]),
    ("陈一然", "positive", "老师对每个小组的追问都很具体，不只是评价好坏，而是指出可以怎么继续改研究问题。", ["反馈", "研究设计"]),
    ("孙浩然", "neutral", "访谈编码演示如果能录屏放到课程群，课后复盘会方便很多。", ["工具", "复盘"]),
    ("林琪", "negative", "课堂讨论里几位同学发言很多，内向的同学不太容易插进去，可以尝试匿名问题池。", ["参与", "匿名"]),
    ("周铭", "positive", "把教育政策文本和学生访谈放在一起比较很有启发，能看到不同材料之间怎么互相验证。", ["材料", "启发"]),
    ("何雨", "neutral", "下次如果继续讲扎根理论，希望能多看一个完整编码过程，而不是只看最后的表格。", ["方法", "编码"]),
    ("赵欣", "positive", "课堂节奏整体舒服，讲授、练习、讨论之间切换很自然，比纯讲课更容易保持注意力。", ["节奏", "体验"]),
    ("王美丽", "negative", "线上同学参与感偏弱，麦克风讨论时听不清，远程同学的反馈容易被忽略。", ["线上", "参与"]),
    ("刘振宇", "positive", "老师最后总结每组的共同问题很有帮助，能让大家知道自己不是孤立地卡在某个点上。", ["总结", "共性问题"]),
    ("陈一然", "neutral", "作业要求可以再明确一点，尤其是引用格式和访谈片段长度，避免大家理解不一致。", ["作业", "规范"]),
]

CANTEEN_CARDS = [
    ("孙浩然", "positive", "新开的清淡窗口很适合晚上自习前吃，口味稳定，排队也比想象中快。", ["口味", "排队"]),
    ("林琪", "negative", "午高峰主食窗口队伍太长，很多同学排到后面就只能随便买，建议加一个临时分流口。", ["排队", "效率"]),
    ("周铭", "neutral", "如果能在入口处显示各窗口预计等待时间，大家会更愿意分散排队。", ["信息", "分流"]),
    ("何雨", "positive", "最近素菜选择变多了，价格也比较友好，对经常在校吃饭的人很重要。", ["价格", "选择"]),
    ("赵欣", "negative", "晚饭后半段热菜补充不稳定，七点以后经常只剩几样，晚课同学选择少。", ["补餐", "晚餐"]),
    ("王美丽", "neutral", "希望能标注常见过敏原，比如花生、虾皮和乳制品，减少大家反复询问窗口阿姨。", ["过敏原", "标识"]),
    ("刘振宇", "positive", "自助称重区结算速度提升明显，扫码和称重之间基本不用等。", ["结算", "效率"]),
    ("陈一然", "negative", "回收区有时候餐盘堆得太满，路过容易堵住，应该安排高峰时段巡回清理。", ["动线", "卫生"]),
    ("孙浩然", "positive", "早餐豆浆和包子组合很稳，价格低，对早八学生很友好。", ["早餐", "价格"]),
    ("林琪", "neutral", "可以试试每周固定一天收集菜单投票，大家会觉得食堂在认真听意见。", ["菜单", "参与"]),
]


def ensure_demo_users(db: Session) -> dict[str, User]:
    users_by_name: dict[str, User] = {}
    for email, nickname, is_admin in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                email=email,
                nickname=nickname,
                password_hash=hash_password("demo123"),
                is_admin=is_admin,
            )
            db.add(user)
        else:
            user.nickname = nickname
            user.is_admin = is_admin
            user.password_hash = hash_password("demo123")
        users_by_name[nickname] = user
    db.flush()
    return users_by_name


def _content_doc(text: str) -> dict:
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def _clear_wall_data(db: Session, wall_id: str) -> None:
    for card in db.scalars(select(Card).where(Card.wall_id == wall_id)).all():
        db.delete(card)
    db.execute(delete(ActionLog).where(ActionLog.wall_id == wall_id))
    db.execute(delete(AiSummaryCache).where(AiSummaryCache.wall_id == wall_id))
    db.execute(delete(ResearchEvent).where(ResearchEvent.wall_id == wall_id))


def _layout_points_for_wall(wall_id: str) -> list[tuple[int, int]]:
    if wall_id == DEMO_WALL_ID:
        return DEMO_OPEN_LAYOUT_POINTS
    return SECONDARY_LAYOUT_POINTS


def _layout_point(idx: int, layout_points: list[tuple[int, int]]) -> tuple[int, int]:
    base_x, base_y = layout_points[idx % len(layout_points)]
    page = idx // len(layout_points)
    return base_x, base_y + page * 2500


def _activity_time(idx: int, reaction_offset: int = 0) -> datetime:
    minutes = idx * 5 + (idx % 3) * 2 + reaction_offset * 3
    seconds = (idx * 17 + reaction_offset * 11) % 53
    return DEMO_ACTIVITY_START + timedelta(minutes=minutes, seconds=seconds)


def _demo_user_list(users_by_name: dict[str, User]) -> list[User]:
    return [users_by_name[nickname] for _email, nickname, _is_admin in DEMO_USERS if nickname in users_by_name]


def _seed_cards(
    db: Session,
    wall_id: str,
    users_by_name: dict[str, User],
    seed_cards: list[tuple[str, str, str, list[str]]],
    *,
    reaction_offset: int = 0,
) -> list[Card]:
    layout_points = _layout_points_for_wall(wall_id)
    cards: list[Card] = []
    for idx, (author_name, sentiment, text, topics) in enumerate(seed_cards):
        author = users_by_name[author_name]
        x, y = _layout_point(idx, layout_points)
        created_at = _activity_time(idx, reaction_offset)
        card = Card(
            wall_id=wall_id,
            author_id=author.id,
            content_json=_content_doc(text),
            plain_text=text,
            x=x,
            y=y,
            color=COLOR_SEQUENCE[(idx + reaction_offset) % len(COLOR_SEQUENCE)],
            rotation=ROTATION_SEQUENCE[(idx + reaction_offset) % len(ROTATION_SEQUENCE)],
            z_index=idx + 1,
            sentiment=sentiment,
            sentiment_confidence=round((82 + ((idx + reaction_offset) % 12)) / 100, 2),
            topic_labels=topics,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(card)
        cards.append(card)
    db.flush()
    users = list(users_by_name.values())
    for idx, card in enumerate(cards):
        pattern_index = (idx + reaction_offset) % len(REACTION_PATTERN)
        target_count = min(REACTION_PATTERN[pattern_index], len(users) - 1)
        added = 0
        cursor = 1
        while added < target_count:
            actor = users[(idx + cursor + reaction_offset) % len(users)]
            cursor += 1
            if actor.id == card.author_id:
                continue
            db.add(
                Reaction(
                    card_id=card.id,
                    user_id=actor.id,
                    reaction_type=REACTION_TYPES[(idx + added + reaction_offset) % len(REACTION_TYPES)],
                    created_at=card.created_at + timedelta(minutes=added + 1, seconds=cursor * 7),
                )
            )
            added += 1
    return cards


def _seed_action_logs(db: Session, wall_id: str, cards: list[Card], users_by_name: dict[str, User], *, reaction_offset: int = 0) -> None:
    users = _demo_user_list(users_by_name)
    admin = users_by_name["崔晓琳"]
    for idx, card in enumerate(cards):
        db.add(
            ActionLog(
                wall_id=wall_id,
                user_id=card.author_id,
                action_type="card:create",
                payload={"card_id": card.id, "x": card.x, "y": card.y, "seeded": True},
                created_at=card.created_at,
            )
        )
        if idx % 4 == 1:
            db.add(
                ActionLog(
                    wall_id=wall_id,
                    user_id=card.author_id,
                    action_type="card:update",
                    payload={"card_id": card.id, "fields": ["content_json", "plain_text"], "seeded": True},
                    created_at=card.created_at + timedelta(minutes=2, seconds=idx * 3),
                )
            )
        if idx % 6 == 2:
            db.add(
                ActionLog(
                    wall_id=wall_id,
                    user_id=card.author_id,
                    action_type="card:move",
                    payload={
                        "card_id": card.id,
                        "from": {"x": card.x - 28, "y": card.y - 18},
                        "to": {"x": card.x, "y": card.y},
                        "seeded": True,
                    },
                    created_at=card.created_at + timedelta(minutes=3, seconds=idx * 5),
                )
            )
        for reaction_idx in range(min(2 + idx % 3, len(users) - 1)):
            actor = users[(idx + reaction_idx + reaction_offset + 1) % len(users)]
            if actor.id == card.author_id:
                actor = users[(idx + reaction_idx + reaction_offset + 2) % len(users)]
            db.add(
                ActionLog(
                    wall_id=wall_id,
                    user_id=actor.id,
                    action_type="card:reaction",
                    payload={
                        "card_id": card.id,
                        "reaction_type": REACTION_TYPES[(idx + reaction_idx) % len(REACTION_TYPES)],
                        "state": "added",
                        "seeded": True,
                    },
                    created_at=card.created_at + timedelta(minutes=4 + reaction_idx, seconds=idx * 2),
                )
            )
    for idx, action_type in enumerate(["wall:organize_topic", "wall:spotlight", "wall:summary", "wall:organize_sentiment"]):
        target_card = cards[(idx * 5 + reaction_offset) % len(cards)] if cards else None
        db.add(
            ActionLog(
                wall_id=wall_id,
                user_id=admin.id,
                action_type=action_type,
                payload={"card_id": target_card.id if target_card else None, "seeded": True},
                created_at=DEMO_ACTIVITY_START + timedelta(minutes=34 + idx * 18, seconds=idx * 7),
            )
        )


def _seed_research_events(db: Session, wall_id: str, cards: list[Card], users_by_name: dict[str, User], *, reaction_offset: int = 0) -> None:
    if not cards:
        return
    users = [user for user in _demo_user_list(users_by_name) if not user.is_admin] + [users_by_name["崔晓琳"]]
    focused_card_ids = {cards[idx].id for idx in [0, 3, 7, 11, 15, 19, 25] if idx < len(cards)}
    event_seq = 0

    def add_event(
        user: User,
        session_id: str,
        event_type: str,
        at: datetime,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        payload: dict | None = None,
    ) -> None:
        nonlocal event_seq
        event_seq += 1
        db.add(
            ResearchEvent(
                wall_id=wall_id,
                user_id=user.id,
                client_session_id=session_id,
                client_event_id=f"{session_id}:{event_seq}",
                event_type=event_type,
                target_type=target_type,
                target_id=target_id,
                x=x,
                y=y,
                viewport_width=1280,
                viewport_height=760,
                canvas_width=1280,
                canvas_height=max(3600, max(card.y for card in cards) + 520),
                payload=payload or {},
                client_ts=at,
                created_at=at + timedelta(milliseconds=280 + event_seq % 120),
            )
        )

    for user_idx, user in enumerate(users):
        session_id = f"rs_demo_{wall_id}_{user_idx + 1}"
        start = DEMO_ACTIVITY_START + timedelta(minutes=user_idx * 4 + reaction_offset, seconds=user_idx * 13)
        add_event(
            user,
            session_id,
            "session:start",
            start,
            target_type="wall",
            payload={"path": f"/wall/{wall_id}", "timezone": "Asia/Singapore", "seeded": True},
        )
        add_event(
            user,
            session_id,
            "wall:view",
            start + timedelta(seconds=12),
            target_type="wall",
            payload={"view_mode": "free", "seeded": True},
        )
        path_length = 9 + (user_idx % 5)
        for step in range(path_length):
            card = cards[(user_idx * 3 + step * 2 + reaction_offset) % len(cards)]
            focus_bonus = 1 if card.id in focused_card_ids else 0
            at = start + timedelta(minutes=2 + step * 5, seconds=(user_idx * 17 + step * 11) % 49)
            jitter_x = ((user_idx + step) % 5 - 2) * 16
            jitter_y = ((user_idx * 2 + step) % 5 - 2) * 13
            point_x = float(card.x + jitter_x)
            point_y = float(card.y + jitter_y)
            add_event(
                user,
                session_id,
                "card:visible",
                at,
                target_type="card",
                target_id=card.id,
                x=point_x,
                y=point_y,
                payload={
                    "ratio": round(0.58 + ((step + user_idx) % 4) * 0.1, 2),
                    "duration_ms": 4600 + step * 520 + focus_bonus * 4200,
                    "view_mode": "free",
                    "seeded": True,
                },
            )
            add_event(
                user,
                session_id,
                "pointer:sample",
                at + timedelta(seconds=18),
                target_type="canvas",
                x=point_x + 22,
                y=point_y - 18,
                payload={"tool": "react" if step % 3 else "add", "seeded": True},
            )
            if step % 3 == 1 or focus_bonus:
                add_event(
                    user,
                    session_id,
                    "ui:click",
                    at + timedelta(seconds=32),
                    target_type="card",
                    target_id=card.id,
                    x=point_x + 8,
                    y=point_y + 4,
                    payload={"view_mode": "free", "seeded": True},
                )
            if step % 4 == 2:
                add_event(
                    user,
                    session_id,
                    "card:detail_open",
                    at + timedelta(seconds=44),
                    target_type="card",
                    target_id=card.id,
                    x=point_x,
                    y=point_y,
                    payload={"plain_text_length": len(card.plain_text), "seeded": True},
                )
            if step % 5 == 3:
                add_event(
                    user,
                    session_id,
                    "stage:scroll",
                    at + timedelta(seconds=56),
                    target_type="wall",
                    y=float(min(card.y + 360, max(0, max(item.y for item in cards) - 420))),
                    payload={"scroll_top": max(0, card.y - 280), "seeded": True},
                )
        if user_idx in {0, 2, 5}:
            add_event(
                user,
                session_id,
                "wall:organize_enter",
                start + timedelta(minutes=48),
                target_type="wall",
                payload={"mode": "topic", "seeded": True},
            )
        if user_idx in {1, 4, 7}:
            add_event(
                user,
                session_id,
                "tool:change",
                start + timedelta(minutes=28),
                target_type="wall",
                payload={"from": "add", "to": "react", "seeded": True},
            )
        add_event(
            user,
            session_id,
            "session:end",
            start + timedelta(minutes=64 + user_idx * 2),
            target_type="wall",
            payload={"duration_ms": (64 + user_idx * 2) * 60 * 1000, "seeded": True},
        )


def _canvas_height(cards: list[Card]) -> int:
    if not cards:
        return 2400
    return max(2400, max(card.y for card in cards) + 420)


def reset_demo_wall(db: Session) -> Wall:
    users_by_name = ensure_demo_users(db)
    db.flush()

    admin = users_by_name["崔晓琳"]
    wall = db.get(Wall, DEMO_WALL_ID)
    if not wall:
        wall = Wall(id=DEMO_WALL_ID, owner_id=admin.id, title="", description="")
        db.add(wall)
    wall.title = "开放交流反馈墙"
    wall.description = "面向课堂、活动或研究组的实时想法收集空间。"
    wall.access_mode = "login_required"
    wall.password_hash = None
    wall.is_anonymous = False
    wall.is_archived = False
    wall.spotlight_card_id = None
    wall.ai_enabled = True
    wall.ai_model = "deepseek-v4-flash"
    wall.ai_thinking_enabled = False
    wall.ai_reasoning_effort = "high"
    wall.owner_id = admin.id

    _clear_wall_data(db, DEMO_WALL_ID)
    db.execute(delete(AuthEvent).where(AuthEvent.email.in_([email for email, _nickname, _is_admin in DEMO_USERS])))

    cards = _seed_cards(db, DEMO_WALL_ID, users_by_name, SEED_CARDS)
    _seed_action_logs(db, DEMO_WALL_ID, cards, users_by_name)
    _seed_research_events(db, DEMO_WALL_ID, cards, users_by_name)
    wall.canvas_height = _canvas_height(cards)
    return wall


def _reset_demo_gallery_wall(
    db: Session,
    users_by_name: dict[str, User],
    *,
    wall_id: str,
    title: str,
    description: str,
    access_mode: str,
    cards: list[tuple[str, str, str, list[str]]],
    reaction_offset: int,
    is_anonymous: bool = False,
    password: str | None = None,
) -> Wall:
    admin = users_by_name["崔晓琳"]
    wall = db.get(Wall, wall_id)
    if not wall:
        wall = Wall(id=wall_id, owner_id=admin.id, title="", description="")
        db.add(wall)
    wall.title = title
    wall.description = description
    wall.access_mode = access_mode
    wall.password_hash = hash_password(password) if password else None
    wall.is_anonymous = is_anonymous
    wall.is_archived = False
    wall.spotlight_card_id = None
    wall.ai_enabled = True
    wall.ai_model = "deepseek-v4-flash"
    wall.ai_thinking_enabled = False
    wall.ai_reasoning_effort = "high"
    wall.owner_id = admin.id

    _clear_wall_data(db, wall_id)
    seeded_cards = _seed_cards(db, wall_id, users_by_name, cards, reaction_offset=reaction_offset)
    _seed_action_logs(db, wall_id, seeded_cards, users_by_name, reaction_offset=reaction_offset)
    _seed_research_events(db, wall_id, seeded_cards, users_by_name, reaction_offset=reaction_offset)
    wall.canvas_height = _canvas_height(seeded_cards)
    return wall


def reset_demo_gallery(db: Session) -> list[Wall]:
    main_wall = reset_demo_wall(db)
    users_by_name = ensure_demo_users(db)
    course_wall = _reset_demo_gallery_wall(
        db,
        users_by_name,
        wall_id=COURSE_WALL_ID,
        title="课程反馈 · 第 4 周",
        description="用于展示课堂评价、助教复盘和研究方法课程讨论。默认登录后参与。",
        access_mode="login_required",
        cards=COURSE_CARDS,
        reaction_offset=2,
    )
    canteen_wall = _reset_demo_gallery_wall(
        db,
        users_by_name,
        wall_id=CANTEEN_WALL_ID,
        title="食堂服务共创墙",
        description="用于展示不同群体、不同权限场景下的意见收集。演示口令 taste123。",
        access_mode="password_required",
        password="taste123",
        cards=CANTEEN_CARDS,
        reaction_offset=5,
        is_anonymous=True,
    )
    return [main_wall, course_wall, canteen_wall]


def ensure_demo_research_data(db: Session) -> None:
    users_by_name = {
        user.nickname: user
        for user in db.scalars(select(User)).all()
        if user.nickname in {nickname for _email, nickname, _is_admin in DEMO_USERS}
    }
    expected_names = {nickname for _email, nickname, _is_admin in DEMO_USERS}
    if not expected_names.issubset(users_by_name):
        users_by_name = ensure_demo_users(db)

    wall_cards = {
        DEMO_WALL_ID: db.scalars(select(Card).where(Card.wall_id == DEMO_WALL_ID).order_by(Card.created_at.asc())).all(),
        COURSE_WALL_ID: db.scalars(select(Card).where(Card.wall_id == COURSE_WALL_ID).order_by(Card.created_at.asc())).all(),
        CANTEEN_WALL_ID: db.scalars(select(Card).where(Card.wall_id == CANTEEN_WALL_ID).order_by(Card.created_at.asc())).all(),
    }
    for offset, (wall_id, cards) in enumerate(wall_cards.items()):
        if not cards:
            continue
        if not db.scalar(select(ActionLog.id).where(ActionLog.wall_id == wall_id).limit(1)):
            _seed_action_logs(db, wall_id, cards, users_by_name, reaction_offset=offset * 2)
        if not db.scalar(select(ResearchEvent.id).where(ResearchEvent.wall_id == wall_id).limit(1)):
            _seed_research_events(db, wall_id, cards, users_by_name, reaction_offset=offset * 2)


def seed_database(db: Session) -> None:
    if db.scalar(select(User).limit(1)):
        ensure_demo_research_data(db)
        db.commit()
        return
    reset_demo_gallery(db)
    db.commit()
