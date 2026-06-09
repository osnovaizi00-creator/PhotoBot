from bot.database.db import Shoot


def format_shoot(shoot: Shoot) -> str:
    phone_line = f"\n📞 Телефон: {shoot.phone}" if shoot.phone else ""
    studio_line = (
        f"\n🏢 Студия/район: <b>{shoot.studio_name}</b>" if shoot.studio_name else ""
    )
    shoot_name_line = (
        f"\n🎬 Название съёмки: <b>{shoot.shoot_name}</b>" if shoot.shoot_name else ""
    )
    return (
        f"🕐 Время: <b>{shoot.shoot_time}</b>\n"
        f"👤 Клиент: <b>{shoot.client_name}</b>\n"
        f"💰 Стоимость: <b>{shoot.cost:,.0f} ₽</b>"
        f"{studio_line}{shoot_name_line}{phone_line}"
    )


def format_shoots_list(shoots: list[Shoot], title: str) -> str:
    if not shoots:
        return f"{title}\n\nНа этот день съёмок нет."
    lines = [title, ""]
    for i, shoot in enumerate(shoots, 1):
        lines.append(f"<b>Съёмка {i}</b>")
        lines.append(format_shoot(shoot))
        lines.append("")
    return "\n".join(lines).strip()
