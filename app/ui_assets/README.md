# Графика приложения и игровых оверлеев

## Оформление «Цветение · ночь»

`blossom-shell-v1.png` — пустая оболочка: фон и внешняя рамка.
`blossom-panel-v2.png` — пустая полупрозрачная панель с мягкой тенью.
`blossom-card-v1.png` — отдельный квадратный материал для высоких карточек,
чтобы не растягивать отражения широкой панели в вертикальные полосы.
Ресурсы созданы встроенным ImageGen по предоставленному пользователем
визуальному образцу. В них нет текста, игровых данных, иконок или кнопок.
`material_assets.py` загружает их из комплекта приложения, масштабирует по
девяти частям и кэширует результат. Углы и толщина рамки не растягиваются вместе
с окном. Активное состояние панели получает усиление яркости и насыщенности.
Генерация изображений и сетевые запросы во время работы приложения не нужны.

Ресурсы применяются только к ночной теме «Цветение» основного окна и окон
с его менеджером материалов. Другие палитры сохраняют прежний способ отрисовки.
При отсутствии PNG используется прежний способ отрисовки. Игровые оверлеи
не переключаются на эти ресурсы. Все файлы уже включаются в Windows-сборку
через существующий `--add-data app/ui_assets;ui_assets`.

Промпт оболочки:

> Use case: precise-object-edit. Production asset for a real desktop application,
> NOT a mockup. Edit the supplied interface image into a completely EMPTY
> application shell. Preserve its beautiful purple-pink faceted glossy beveled
> outside frame, exactly its restrained thickness, rounded chamfered corners,
> delicate pink and lilac specular edges, and the dark plum atmospheric background
> with soft mauve clouds. Remove ALL text, numbers, logos, icons, buttons, cards,
> panels, lines, controls, sidebar divisions, and all interface content. Extend
> the empty background naturally into the areas that were covered by UI.
> Background mostly very dark plum, soft nonuniform pink-violet smoky reflections
> concentrated near upper right and lower left, subdued center for readability.
> Keep outer frame around the whole perimeter, flush near the image edges as in
> reference. Front-on orthographic, perfectly rectangular widescreen 16:9 image,
> preferably 1536x864. No perspective, no objects, no fantasy decorations, no
> branches or blossoms, no stars, no words or glyphs whatsoever. Exact original
> reference material style and brightness. This asset will be rendered behind
> live native controls.

Промпт панели:

> Use case: precise-object-edit. Extract and clean the large statistics panel from
> the reference screenshot (the horizontal panel with 617 / 51.7% / 2.33 / 6.3).
> Produce ONE EMPTY panel, remove all text, figures and internal separators,
> naturally restoring its glass material underneath. Preserve the reference
> panel itself as faithfully as possible: very subtle THIN soft mauve perimeter,
> NO double border, NO bright neon edges, NO heavy bevel. Matte-satin dark plum
> translucent glass, nuanced broad softly diffused pink/lilac reflections,
> lighter at upper left and upper right but very diffuse, soft interior shadow
> at bottom and gentle black drop shadow below. Rounded corners radius about
> 12px at original width1240px and height100px. No hard reflective streaks,
> no bright spotlights, no chrome, no decoration. Single blank panel with same
> proportions as the reference, very wide and low approximately 12:1. Place it
> across the middle of canvas if necessary. True transparent surrounding area
> with alpha. All typography and UI content completely removed. This is a
> production UI background asset to put behind real text, not a whole UI mockup.
> The reference is the approved target: copy the subtle reference material,
> don't exaggerate it.

Промпт квадратной карточки:

> Use case: style-transfer. Production EMPTY square UI card background texture,
> not a mockup. Style reference is the supplied purple desktop UI. Generate one
> single rounded square panel, occupying almost the entire square image with
> only a thin transparent margin for shadow. No text or content at all. Dark plum
> satin frosted glass, delicate soft rose and lavender reflected ambient light
> spread across the top and upper corners, slight mottled diffuse texture.
> Subdued dark purple center for readability. Thin subtle lavender perimeter,
> softly rounded small corners (about4% of width), tiny highlight on top rim,
> soft black drop shadow below. No double border, no bright neon, no vertical
> streaks, no columns, no chrome. Smooth broad diffuse reflections similar to the
> reference stats panel but designed for a SQUARE compact card. True alpha
> transparency outside the square. No letters, numbers, symbols, dividers,
> controls, icons, objects, or decoration. This is a reusable nine-slice UI
> artwork to put behind live profile/rank/statistic data.

## Графика игровых оверлеев

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
