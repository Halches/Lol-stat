# Графика игровых оверлеев

`hextech-panel.png`, `hextech-badge.png`, `objective-portraits.png` — оригинальная
графика, созданная встроенным ImageGen по согласованным макетам. Панель имеет
фактурную тёмную подложку и золотую фаску, масштабируется по девяти частям.
Щиток — пустая рамка; числа и стрелка остаются динамическими. Атлас 2×2 содержит
иллюстрации категорий: дракон, личинка, Барон, Герольд. Это иллюстрации, не данные API.
Все файлы включены в EXE и не скачиваются во время игры.

Цифры рисуются шрифтом Cinzel (Google Fonts, лицензия OFL в app/fonts/OFL-cinzel.txt),
а не запекаются в PNG с демонстрационными значениями.

## Исходная стрелка (совместимость)

`tab-advantage-arrow.png` is an original generated transparent PNG, made with the
built-in imagegen tool for this project. The full source is retained here; the
renderer crops transparent margins, scales it to the centre gutter and rotates
it 180 degrees when the player on the right has the advantage. No recolouring or
runtime image download is required. Included in the Windows EXE as `ui_assets`.

Generation prompt:

> A single compact horizontal left-pointing UI arrow for a League of Legends
> companion overlay. League of Legends / Hextech interface aesthetic: crisp angular
> beveled antique-gold metal edges, very dark navy recessed interior, subtle pale
> cyan accent. Strong simple silhouette, short shaft, substantial arrowhead,
> readable at about 28 by 14 pixels. Flat orthographic front view, vertically
> symmetric silhouette so a 180-degree rotation reverses the direction. Genuinely
> transparent background. No text, numbers, logo, panel, extra arrows or external glow.
