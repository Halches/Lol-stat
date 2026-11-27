# Нарисованные поверхности «Цветение»

Созданы встроенным ImageGen по предоставленному пользователем исходному образцу.
Файлы PNG сохранены с исходным альфа-каналом. Текст и иконки в них отсутствуют.
Программа выделяет прямоугольник поверхности и масштабирует его по девяти частям;
исходные изображения не перезаписываются. Сеть при запуске не нужна.

## blossom-panel-v1.png

Use case: precise-object-edit. Input image is the exact reference UI. Produce a production-ready empty raster UI material: extract and reconstruct ONLY its large horizontal statistics panel (the panel behind 617, 51.7%, 2.33, 6.3). Remove all words, digits, dividers, icons, and all other UI. One empty very wide rounded rectangular panel, straight orthographic front view. The panel itself has width:height about 10:1, occupying almost all canvas width, centered on an actually transparent canvas. Match the reference closely: smoky plum translucent glass, softly luminous mauve upper surface, darker violet lower surface, irregular broad satin reflections, subtly brighter upper left and upper right, thin delicate lilac rim, soft dark shadow just beneath. Corners subtly rounded, not pills. Refined subtle depth, no thick bevel, no neon, no chrome, no sharp white line, no decorations or particles. Keep entire panel including shadow within image. No text anywhere. Preserve real alpha transparency outside and partial transparency in glass. This asset will be stretched with nine-slice rendering behind live text.

## blossom-button-v1.png

Use case: precise-object-edit. Input is reference UI. Extract and reconstruct ONLY the inactive rounded button surface matching the button labeled Поражения. Remove the label and all other UI. Single EMPTY horizontal rounded rectangular button with width:height about 4.3:1. On actually transparent canvas, front-on orthographic view, button occupying 90% canvas width, all edges and subtle shadow visible. Precisely match its dark smoky plum glass, muted lavender highlight on upper edge, rounded bevel, dark lower center, gentle reflected mauve light on bottom edge. The surface must have soft nuanced irregular illumination and subtle glass depth, not a flat gradient and not a metallic frame. No letters, no symbols, no icons, no glow rays, no hard white lines. A reusable clean empty UI skin, real alpha outside, partially translucent interior.

## blossom-selected-v1.png

Use case: precise-object-edit. Input is reference UI. Extract and reconstruct ONLY the selected pink-lilac button surface matching Сохранённые матчи. Remove the label and all other UI. Single EMPTY horizontal rounded rectangular button with width:height about 4.3:1 on actual transparent canvas. Front-on orthographic, occupies 90% canvas width, all corners and soft outer shadow visible. Precisely match reference: satin lilac glass, pale pink upper-left highlight, gently luminous mauve top, deeper plum center, luminous lavender lower rim, restrained soft pink-lilac halo. Rounded corners, small smooth bevel, delicate reflections. No thick chrome border, no bright white stripe, no neon rays, no crystals, no decorations. No text or symbols. Real alpha outside and subtle translucent glass inside. This is a production UI skin behind live text.
