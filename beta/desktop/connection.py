"""User-facing connection states shared by the dashboard and API."""


def connection_view(snapshot):
    raw = snapshot.get("connection")
    if not isinstance(raw, dict):
        profile = (snapshot.get("homeProfile") or {}).get("profile") or {}
        raw = {"state": "ready" if profile else "offline" if snapshot.get("phase") == "offline" else "loading_profile",
               "profileAvailable": bool(profile), "history": "available" if (snapshot.get("homeProfile") or {}).get("historyAvailable") else "unavailable"}
    state = raw.get("state", "offline")
    title, message, hint = {
        "offline": ("Подключите клиент LoL", "Откройте League of Legends и войдите в аккаунт EUW.",
                    "Матч запускать не нужно. Пока можно посмотреть сборки или проверить голос."),
        "connecting": ("Подключаемся к клиенту", "Клиент найден. Проверяем регион и доступ к аккаунту.",
                       "Если клиент ещё запускается, дождитесь его главного экрана."),
        "loading_profile": ("Загружаем профиль", "Клиент EUW подключён. Получаем профиль, ранги и историю.",
                            "Сборки и проверка голоса уже доступны."),
        "profile_error": ("Профиль пока недоступен", "Клиент найден, но ещё не отдал данные аккаунта.",
                          "Убедитесь, что вход завершён, затем повторите подключение. Повторим проверку и автоматически."),
        "unsupported_region": ("Другой регион", "Эта версия работает с аккаунтами EUW.",
                               "Просмотр сборок и проверка голоса доступны независимо от региона."),
        "in_match": ("Матч идёт", "Профиль и история обновятся после выхода в меню клиента.", ""),
        "ready": ("Клиент LoL подключён", "Профиль загружен.", ""),
    }.get(state, ("Проверяем подключение", "Обновляем состояние клиента.", ""))
    if state == "ready":
        history = raw.get("history")
        if history == "cached":
            message = "Профиль загружен. Показываем сохранённую историю: источник временно недоступен."
        elif history == "unavailable":
            message = "Профиль загружен. Клиент пока не отдаёт историю матчей."
        elif raw.get("refreshing"):
            message = "Профиль загружен. Обновляем историю в фоне."
    if raw.get('profileCached'):
        if state == 'offline':
            title = 'Сохранённый профиль'
            message = 'Клиент LoL закрыт. Показываем последний аккаунт и загруженную историю.'
            hint = 'При запуске клиента проверим аккаунт и обновим данные автоматически.'
        else:
            message += ' Пока показываем последний сохранённый аккаунт; текущий вход ещё не подтверждён.'
    return dict(raw, title=title, message=message, hint=hint)
