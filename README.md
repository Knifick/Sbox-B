# Sobixel и SboxB: руководство для агентов

Как собирать игры для **Sobixel**, мобильного конструктора на Solar2D/Lua 5.1. Если пользователь просит
**3D-игру**, её делают поверх набора скриптов **SboxB**: 3D-рендер, GameObject/компоненты, физика,
FPS-игрок, свет и скайбокс.

Всё ниже проверено на распакованных проектах и на рабочих сборках. Места, где поведение
выведено из наблюдений, а не из документации, помечены **(наблюдение)**.

---

## Где взять Sbox B

**Репозиторий: https://github.com/Knifick/Sbox-B**

**Скачать `SboxB.sobixel`: https://github.com/Knifick/Sbox-B/raw/main/SboxB.sobixel**

Файл лежит в корне репозитория рядом с этим README: [SboxB.sobixel](SboxB.sobixel). Его можно открыть на GitHub
и нажать **Download raw file**. Агенту быстрее скачать напрямую:
`curl -L -o SboxB.sobixel https://github.com/Knifick/Sbox-B/raw/main/SboxB.sobixel` или
`git clone https://github.com/Knifick/Sbox-B`.

Как пользоваться:
- Скачанный файл откройте в Sobixel (импорт проекта `.sobixel`). При первом запуске появится демо-сцена:
  пол, стены, ящики и мяч, которые можно поднять кнопкой USE, солнце, лампа, небо. Управление сенсорное.
- Агенту этот файл служит **базой**: распакуйте zip, оставьте скрипты 1, 2, 4, 11, 12, 15–22 как есть, замените
  Script5 (демо-сцену) и добавьте свои скрипты с id от 23 и выше. Затем соберите zip по правилам раздела 2.4.
- Рядом лежат два инструмента (Python 3):
  - [`tools/luamin.py`](tools/luamin.py) — минификатор и валидатор Lua для `requestApi`:
    `python3 tools/luamin.py in.lua > out.txt`. Для проверки синтаксиса нужен `luac5.1`, без него — флаг `--no-luac`;
  - [`tools/pack_sobixel.py`](tools/pack_sobixel.py) — распаковать проект, добавить Lua-скрипт, собрать обратно:
    ```sh
    python3 tools/pack_sobixel.py unpack SboxB.sobixel proj/
    python3 tools/pack_sobixel.py script proj/ 23 "My game" game.lua
    python3 tools/pack_sobixel.py pack proj/ MyGame.sobixel
    ```

Что внутри шаблона:

| Script | Назначение |
|---|---|
| 1 Renderer, 2 Camera, 4 Controls (FPS) | рендер, камера и `deltaTime`, сенсорное управление |
| 11 GameObject Core, 12 Mesh, 15 GameObject, 16 OBJ Loader | объекты, компоненты, встроенные меши, загрузка OBJ |
| 17 Lighting, 19 Skybox, 18 Editor | свет, небо, значки света в редакторе |
| 20 Physics, 21 Player | физика твёрдых тел, FPS-игрок |
| 22 API Reference (Project) | справка по всем функциям и путям `EditGameObject` |
| 5 Scene | **демо-сцена**, заменяется вашей игрой |

Картинки: `stone`, `skybox_0`, `sbox_empty`, значки редактора света.

---

## 0. Короткий чек-лист

1. Код пиши обычными `.lua`-файлами, потом минифицируй в одну строку и проверь (раздел 3.3).
2. Каждый модуль кладётся в отдельный скрипт: блок `onStart` и в нём один блок `requestApi` с текстом кода.
3. Модули стартуют параллельно и в любом порядке, поэтому каждый ждёт готовности зависимостей:
   `R.ready`, `R.physicsReady`, `E.SBOX3D_NEW`… Ожидание делают через `timer.performWithDelay(16, boot)`.
4. Кадровый цикл: `table.insert(E.GAME_conditions, tick)`. Блок `forever` не нужен.
5. 3D: оставь скрипты SboxB 1, 2, 4, 11, 12, 15–22 без изменений. Сцену собирай через
   `E.SBOX3D_NEW/ADD/EDIT`, камеру ставь через переменные проекта `camX/camY/camZ/yaw/pitch/roll`.
6. Углы задаются **в градусах**. Ось Y смотрит вверх, единица длины — метр. `builtin:cube` имеет размер 2×2×2,
   поэтому для него `boxcollider.size = 2`.
7. Собирай zip так же, как пишет Sobixel (раздел 2.4), и проверяй его в мок-харнессе до отдачи пользователю.

---

## 1. Что такое Sobixel

- Мобильный конструктор игр. Внутри движок Solar2D (Corona), язык Lua 5.1.
- Игра состоит из **скриптов-блоков** (визуальное программирование). У каждого скрипта есть события
  (`onStart`, вызов функции и т.д.) и действия: `setVar`, `if`, `forever`, `readFileRes`, `requestApi` и другие.
- Блок `requestApi` выполняет **произвольный Lua-текст**. Почти весь серьёзный код живёт в нём.
- Проект — это файл `.sobixel`, обычный zip с JSON-скриптами, картинками и ресурсами.
- В Lua доступно всё API Solar2D: `display` (включая `newMesh` с `hasZ`), `graphics.defineEffect` с шейдерами,
  `timer`, `system`, `io` (запись в `TemporaryDirectory`/`DocumentsDirectory`), `audio`, `native`, `Runtime`.
  Есть и сеть: `require("socket")` иногда доступен через `print5`.

---

## 2. Структура проекта `.sobixel`

### 2.1 Записи zip

| Запись | Что это |
|---|---|
| `game.json` | манифест: заголовок, порядок скриптов, функции/переменные проекта, ресурсы, папки |
| `Scripts/ScriptN` | один скрипт = JSON (формат ниже). **N — числовой id**, Sobixel не переиспользует id: новые бери больше максимального |
| `Images/ImageN` | картинки (PNG); в коде они доступны по имени из `game.json` |
| `Resources/ResourceN` | произвольные бинарные ресурсы (раздел «others» в `game.json`); читаются блоком `readFileRes` |
| `Scenes/Scene1/scene.json` | сцена (`{"title":"Сцена 1","comment":false,"objects":[]}`) |
| `hash.txt` (пустой), `custom.json` (`{"len":0}`), `icon.png` | служебные |
| каталоги `Scenes/`, `Resources/`, `Levels/`, `Images/`, `Sounds/`, `Fonts/`, `Videos/`, `Scripts/` | отдельные записи-каталоги |

### 2.2 `game.json` (важные поля)

```json
{
  "build": "1483", "title": "My Game", "link": "...", "id": "...", "created": "...",
  "settings": {"build": 5, "version": "1.0", "package": "com.example.app...", "orientation": "landscape"},
  "scripts": [56, 2, 1, 4, 11, 20, 12, 16, 15, 17, 19, 5, 18, 21, 22, 57, 58],
  "funs": ["newMeshObject", "newGameObject", "addComponent", "EditGameObject", "newLightSource", "LoadOBJModel",
           "setHemisphereAmbient", "setSkybox", "PhysicsAddForce", "PhysicsAddTorque", "PhysicsExplosion",
           "PhysicsSetGravity", "PhysicsTune", "PhysicsRaycast"],
  "vars": ["camX", "camY", "camZ", "yaw", "pitch", "roll", "deltaTime", "rayHit", "rayDist", "rayX", "rayY", "rayZ",
           "rayNX", "rayNY", "rayNZ", "inMoveX", "inMoveZ", "inJump", "inSprint", "inCrouch", "inInteract", "inFly",
           "playerState", "playerGrounded", "playerSpeed"],
  "tables": [],
  "resources": {
    "images": [["stone", "nearest", "Image2"], ["skybox_0", "linear", "Image14"]],
    "others": [["level.dat", "Resource2"]],
    "fonts": [], "videos": [], "sounds": [], "levels": [], "scenes": [["Сцена 1", "Scene1"]]
  },
  "folders": { "scripts": [["1", [2, 1, 4], false], ["mygame", [56, 57, 58], false]], "images": [...], "others": [...] }
}
```

- `scripts` — порядок скриптов в проекте. Все `onStart` стартуют в начале сцены. На строгий порядок не
  полагайся, жди готовности сам.
- `funs` и `vars` — **функции и переменные проекта**. Каждую, к которой обращаются блоки, нужно перечислить
  здесь.
- `images`: `[имя, "nearest"|"linear", "ImageN"]`. Фильтр SboxB учитывает и для текстур мешей.
- `id`, `link`, `build`, `created`, `settings` бери из исходного проекта пользователя и не меняй.

### 2.3 Формат скрипта

```json
{"title": "My module", "funs": [], "tables": [], "vars": ["mySceneVar"], "comment": false,
 "params": [
   {"tables": [], "vars": [], "name": "onStart", "event": true, "nested": [], "comment": false, "params": [[["My module", "t"]]]},
   {"name": "requestApi", "event": false, "comment": false, "params": [[["<однострочный Lua>", "t"]]]}
 ]}
```

`params` — плоский список блоков. Событие (`"event": true`) начинает новую цепочку, действия после него
относятся к этому событию. Список `vars` скрипта объявляет **переменные сцены**.

Блоки, встречавшиеся в рабочих проектах **(наблюдение)**:

| Блок | params |
|---|---|
| событие `onStart` | `[[["подпись", "t"]]]` или `[[]]` |
| событие `onFun` (функция сцены) | `[[["имя", "fS"]]]` |
| событие `onFunParams` (функция проекта с аргументами) | `[[["имя", "fP"]], [["table", "tE"]]]`; аргументы лежат в `E.G_tablesE.table[1..n]`. В объявлении события есть `"tables": ["table"]` |
| `setVar` | `[[["var", "vS"/"vP"/"vE"]], [выражение]]` |
| `requestApi` | `[[["lua", "t"]]]` |
| `requestFun` | `[[["имя", "fS"]]]` |
| `requestFunParams` | `[[["имя", "fP"]], [аргументы через ["," , "s"]]]` |
| `forever` / `foreverEnd`, `if` / `ifEnd` | цикл и условие |
| `readFileRes` | `[[["nameVar", "vE"]], [["outVar", "vE"]], [["inputDefault", "sl"]]]`: читает ресурс (имя из `others`) в переменную как строку байтов |
| `comment` | `[[["текст", "t"]]]` |

Токены выражений `[значение, тип]` **(наблюдение)**:
- `n` — число, `t` — текст;
- `s` — символ (скобки, запятая, арифметика), `l` — логика (`==`, `and`, `true`);
- `vS`/`vP`/`vE` — переменная сцены, проекта, события; `tE` — таблица события;
- `fS`/`fP` — функция сцены или проекта; `f` — встроенная функция (например `timer`).

### 2.4 Требования к zip (иначе Sobixel может не открыть проект)

- version made by `0x0314`, version needed 20, flag bits 0. Без extra-полей, data descriptor и комментариев.
- Каталоги хранятся stored с `external_attr = 0x41c00000`. Файлы — deflate с `0x81800000`. Пустой `hash.txt` — stored.
- Порядок записей: `Scenes/Scene1/`, `Scenes/Scene1/scene.json`, `Scenes/`, `Resources/*`, `Resources/`,
  `Levels/`, `Images/*`, `Images/`, `Sounds/`, `Fonts/`, `Videos/`, `Scripts/*`, `Scripts/`, `game.json`,
  `hash.txt`, `custom.json`, `icon.png`.
- Неизменённые записи исходного проекта лучше переносить **сырыми deflate-потоками** с исходными CRC и временем.
- JSON сериализуй компактно: `separators=(',', ':')`, `ensure_ascii=False`, UTF-8.

Всё это делает [`tools/pack_sobixel.py`](tools/pack_sobixel.py) (команда `pack`).

---

## 3. Lua внутри `requestApi`

### 3.1 Окружение

```lua
local D = print5("debug")          -- debug-библиотека
local E = D.getfenv(print5)        -- настоящее глобальное окружение Solar2D
```

Что есть в `E`:
- Solar2D: `E.display`, `E.timer`, `E.system`, `E.graphics`, `E.audio`, `E.io`, `E.native`, `E.Runtime`,
  `E.math`, `E.string`. Глобальный `display` тоже доступен.
- `E.G_varsP` — переменные проекта, `E.G_varsS` — сцены, `E.G_varsE` — события.
- `E.G_tablesE` — таблицы события (аргументы `onFunParams`), `E.G_funsP` — функции проекта.
- `E.G_other.getImage(name)` возвращает файл картинки проекта (лежит в `system.DocumentsDirectory`).
- `E.GAME.RESOURCES.images` — список картинок из `game.json`.
- `E.GAME_conditions` — **таблица функций, которые Sobixel вызывает каждый кадр**. Через неё делают цикл.
- `E.G_math` — математика блоков Sobixel. **Работает в градусах**: `G_math.cos(180) = -1`. Обычный `E.math`
  работает в радианах.

Сцена (stage) берётся так: `local stage = display["get" .. "CurrentStage"]()`. Литерал запрещён, см. ниже.

### 3.2 Жёсткие ограничения на текст кода

Это ограничения Sobixel и цепочки JSON → Sobixel → `loadstring`:

- **Одна физическая строка**: никаких `\n`, `\r`, `\t`.
- **Никаких обратных слэшей** (даже в строках). Нужный символ собирай через `string.char(92)` или
  `string.char(10)`.
- Никаких `--`: комментарий съест остаток строки. Минификатор выкидывает все комментарии.
- Никаких long brackets `[[`, `]]`, `[=[`. Вложенные индексы `a[b[c]]` пиши через пробел: `a[b[c] ]`.
- Только ASCII в коде. Русский текст храни в данных или в блоках `comment`.
- **Нельзя писать литерал `getCurrentStage`**, используй `display["get" .. "CurrentStage"]()`.
- **Нельзя `pcall(function`** (и `xpcall(function`). Sobixel переписывает этот текст в `SAFE_RUN`, которого нет
  в окружении. Используй именованную функцию: `local function f() ... end pcall(f)`.
- Ограничения Lua 5.1: **≤ 200 локальных на функцию, ≤ 60 upvalue**, нет `goto`, нет битовых операторов.
  Модуль, обёрнутый в одну функцию, легко упирается в 200 локальных: группируй их в таблицы.

### 3.3 Как писать код (рекомендуемый конвейер)

1. Пиши обычные многострочные `.lua`-модули с комментариями.
2. Прогоняй каждый через минификатор с валидатором: [`tools/luamin.py`](tools/luamin.py), функция
   `minify(src, name)` или CLI. Она:
   - токенизирует;
   - убирает комментарии и лишние пробелы;
   - проверяет все запреты выше;
   - вызывает `luac5.1 -p`.
3. Модуль оборачивай в фабрику, чтобы контролировать порядок инициализации:
   ```lua
   do local D=print5("debug") local E=D.getfenv(print5) E.XSM=E.XSM or {} E.XSM["mymod"]=function(X) <код> end end
   ```
   Отдельный boot-скрипт ждёт появления всех `E.XSM[...]` и вызывает их по порядку.
4. Перед отдачей прогоняй проект в мок-харнессе (раздел 6).

### 3.4 Типовые приёмы

```lua
-- ожидание готовности (модули стартуют в любом порядке)
local tries = 0
local function boot()
  tries = tries + 1
  local R = findSbox()                         -- см. раздел 4.2
  if not (R and R.ready and R.physicsReady and E.SBOX3D_NEW) then
    if tries < 600 then E.timer.performWithDelay(16, boot) end
    return
  end
  -- ... инициализация ...
end
E.timer.performWithDelay(1, boot)

-- покадровый цикл
local last = E.system.getTimer()
local function tick()
  local now = E.system.getTimer()
  local dt = math.min(0.05, (now - last) / 1000)
  last = now
  -- ... логика ...
end
if type(E.GAME_conditions) == "table" then table.insert(E.GAME_conditions, tick)
else E.Runtime:addEventListener("enterFrame", tick) end

-- ловля ошибок вместо падения проекта
local function onErr(ev) E.print("ERR " .. tostring(ev.errorMessage)) return true end
E.Runtime:addEventListener("unhandledError", onErr)
```

- **Бинарные данные** (уровни, звуки, модели) кладутся ресурсом в `others`. Скрипт-загрузчик содержит
  `setVar name = "file.dat"`, затем `readFileRes`, затем `requestApi`, который забирает `E.G_varsE.<outVar>`.
- **Звук из байтов**: запиши файл в `system.TemporaryDirectory` через `E.io.open(path, "wb")`, затем
  `audio.loadSound(fname, system.TemporaryDirectory)`.
- **Текстура из пикселей**: сгенерируй PNG или BMP (без zlib: stored-deflate PNG или BMP), запиши в
  `TemporaryDirectory` и используй как `fill = {type="image", filename=..., baseDir=...}`.
- **Перезапуск сцены в редакторе**: при старте снимай свои слушатели и группы от прошлого запуска. Храни ссылки
  в `E.MYGAME` и вызывай `E.MYGAME.Shutdown()` перед повторной инициализацией.
- **Мультитач**: `pcall(E.system.activate, "multitouch")`.

---

## 4. 3D-игры на SboxB

### 4.1 Состав SboxB (оставляй как есть)

| Script | Название | Что делает |
|---|---|---|
| 1 | Renderer | создаёт шейдеры, выбирает бэкенд глубины, `E.SBOX3D_RENDER` (рендер всех GameObject) и цикл `renderSceneV2` |
| 2 | Camera | `deltaTime`, инициализация `camX/camY/camZ/yaw/pitch/roll`, FPS-текст (переменная сцены `showDebug`) |
| 4 | Controls (FPS) | сенсорный стик, взгляд пальцем, кнопки. Пишет `inMoveX/inMoveZ/yaw/pitch/inJump/inSprint/inCrouch/inInteract/inFly` |
| 11 | GameObject Core | `E.SBOX3D_NEW/ADD/EDIT` и блок-функции `newGameObject/addComponent/EditGameObject` |
| 12 | Mesh | встроенные меши `builtin:cube/plane/sphere/capsule` в `R.meshAssets` |
| 15 | GameObject | блок-функция `newMeshObject(name, meshId, texture, x, y, z, size)` |
| 16 | OBJ Model Loader | `LoadOBJModel(resourceName)` → меш `model:<resourceName>` |
| 17 | Lighting | `newLightSource(...)`, `setHemisphereAmbient(...)` |
| 18 | Editor | значки источников света при `isEditor = true` |
| 19 | Skybox | `setSkybox(name, exposure, syncLighting)` (картинка `skybox_0`) |
| 20 | Physics | физика твёрдых тел, рейкаст, PlayerController |
| 21 | Player | создаёт GameObject `Player` (капсула + PlayerController), ведёт камеру, подбор и бросок предметов |
| 22 | API Reference | справка-комментарии (полный список путей `EditGameObject`) |

Нужные картинки: `skybox_0` (Image14), `sbox_empty` (Image15), значки редактора (Image9–13), `stone` (Image2).
Script5 («Scene») — это место для **твоих** настроек сцены. Перепиши его под игру.

**Важно:** база — файл [SboxB.sobixel](https://github.com/Knifick/Sbox-B/raw/main/SboxB.sobixel) из раздела «Где взять Sbox B». Агент добавляет свои
скрипты с id больше максимального (от 23). Скрипты SboxB не трогает, кроме Script5.

### 4.2 Корень и состояние

```lua
local function findSbox()
  local s = display["get" .. "CurrentStage"]()
  for i = 1, s.numChildren do
    local g = s[i]
    if g and g.objects and g.objects3d then
      g.objects3d.cc3dV2 = g.objects3d.cc3dV2 or {}
      return g.objects3d.cc3dV2, g     -- R (состояние SboxB), root (группа рендера)
    end
  end
end
```

Поля `R`:
- `R.ready` — рендер готов. `R.physicsReady` — физика готова. `R.playerReady` — игрок создан.
- `R.backend`: `"gpu-z"` или `"sorted"`.
- `R.gameObjects["go-<name>"]`, `R.meshAssets[id]`, `R.lights`, `R.lightOrder`.
- `R.ambientSky`, `R.ambientGround`, `R.ambientIntensity`.
- `R.renderedObjects`, `R.culledObjects`, `R.physicsStats`.

### 4.3 Система координат и камера

- **Y вверх**, единицы — **метры** (гравитация по умолчанию −9.81).
- Углы (`Transform.rotation`, `yaw`, `pitch`, `roll`) — **в градусах**.
- Направление взгляда: `forward = (sin(yaw)·cos(pitch), sin(pitch), cos(yaw)·cos(pitch))`. При `yaw = 0` камера
  смотрит на +Z, при `pitch > 0` — вверх.

  ```lua
  local K = R.eulerScale or 1     -- 180/pi, если G_math работает в градусах
  local yr, pr = yaw / K, pitch / K
  local fx, fy, fz = math.sin(yr) * math.cos(pr), math.sin(pr), math.cos(yr) * math.cos(pr)
  ```
- Камера задаётся переменными проекта `E.G_varsP.camX/camY/camZ/yaw/pitch/roll`. Рендер читает их каждый кадр.
- Переменные сцены рендера (`E.G_varsS`):
  - `near` (0.01), `focalLength` (300 — фокус в пикселях контента, задаёт FOV);
  - `renderDistanceSq` (100000 = 316 м);
  - `depthBackend` (`auto|arm|ext|nv|sorted`), `depthBits` (14 или 8), `showDebug`.

### 4.4 GameObject и компоненты

Создание (Lua; блочные аналоги — `newGameObject/addComponent/EditGameObject`):

```lua
local N, A, X = E.SBOX3D_NEW, E.SBOX3D_ADD, E.SBOX3D_EDIT
N("Crate1", 2, 1, 5)                            -- имя, x, y, z
A("Crate1", "MeshFilter")    X("Crate1", "meshfilter.mesh", "builtin:cube")
A("Crate1", "MeshRenderer")  X("Crate1", "meshrenderer.texture", "stone")   -- имя картинки проекта
X("Crate1", "scalex", 0.5) X("Crate1", "scaley", 0.5) X("Crate1", "scalez", 0.5)
A("Crate1", "BoxCollider")   X("Crate1", "boxcollider.size.x", 2) X("Crate1", "boxcollider.size.y", 2) X("Crate1", "boxcollider.size.z", 2)
A("Crate1", "PhysicsBody")   X("Crate1", "physicsbody.mass", 8)
X("Crate1", "tag", "grabbable")                 -- Player умеет брать предметы с тегом grabbable
```

- Объект хранится в `R.gameObjects["go-Crate1"]`: `{name, active, activeSelf, tag, layer, components = {Transform, MeshFilter, ...}}`.
  Имя можно передавать как `"Crate1"` или `"go-Crate1"`.
- `Transform`: `position{x,y,z}`, `rotation{x,y,z}` (градусы), `localScale{x,y,z}`, `size` (общий множитель).
- Компоненты можно читать и менять напрямую: `o.components.Transform.position.x = 3`. После смены меша или
  материала выставляй `MeshRenderer.dirty = true`. После смены формы коллайдера или массы — `PhysicsBody._massDirty = true`.
  Тело, которое двигаешь вручную, буди: `pb.sleeping = false` или `E.SBOX3D_PHYS_WAKE(o)`. `EDIT` делает всё это сам.
- Скрыть объект: `X(name, "active", false)`. Удалить: `R.gameObjects["go-"..name] = nil`. Рендер сам уберёт его
  нативные меши. **(наблюдение)** Перед удалением тела с физикой выключи его, иначе оно останется в списке физики.
- Полный список путей `EditGameObject` — в Script22. Основные префиксы:
  - `transform.*` (`x/y/z/rotx/roty/rotz/scalex/.../size`), `active`, `tag`, `layer`;
  - `meshfilter.mesh`, `meshrenderer.texture`;
  - `lightsource.*`, `physicsbody.*`, `boxcollider.*`, `spherecollider.*`, `capsulecollider.*`, `playercontroller.*`.

### 4.5 Меши

- Встроенные меши:
  - `builtin:cube` — куб от −1 до 1, **ребро 2**;
  - `builtin:plane` — квадрат 2×2 в плоскости XY, нормаль +Z;
  - `builtin:sphere` — радиус 1;
  - `builtin:capsule` — радиус 0.5, высота 2, ось Y.
- **Свой процедурный меш** — регистрируй ассет:
  ```lua
  R.meshAssets["my:ramp"] = {
    id = "my:ramp",
    vertices = { x1,y1,z1, x2,y2,z2, ... },     -- плоский массив
    uvs      = { u1,v1, u2,v2, ... },
    normals  = { nx1,ny1,nz1, ... },            -- нужны для освещения
    subMeshes = { { indices = { 1,2,3, 1,3,4, ... }, materialIndex = 1 } },  -- индексы с 1
    bounds = { x = 0, y = 0, z = 0, r = <радиус описанной сферы> },          -- для отсечения
  }
  X("Ramp", "meshfilter.mesh", "my:ramp")
  ```
  - Порядок вершин в треугольниках бери как у `builtin:cube` (`1,2,3, 1,3,4` на грань). Если грани не видны,
    разверни порядок индексов: бэкенд `gpu-z` отбрасывает «лицевые» по своей проекции грани.
  - Несколько материалов: несколько `subMeshes` с разными `materialIndex` и `MeshRenderer.materials[i]`.
- **OBJ**: положи `.obj` ресурсом (`others`), вызови `LoadOBJModel("ship.obj")`, затем
  `meshfilter.mesh = "model:ship.obj"`.

### 4.6 Материалы и текстуры

- `meshrenderer.texture = "<имя картинки проекта>"` создаёт `materials[1] = {link, base = DocumentsDirectory, textureName}`.
- Сгенерированная в рантайме текстура:
  ```lua
  local mr = o.components.MeshRenderer
  mr.materials = { { link = "my_tex.png", base = E.system.TemporaryDirectory, textureName = "my_tex" } }
  mr.dirty = true
  ```
- Пиксельная фильтрация (`nearest`): укажи `"nearest"` у картинки в `game.json`. Для своих файлов заведи
  `R.imageFilters["my_tex"] = "nearest"`.
- Прозрачность: пиксели с alpha < 0.01 отбрасываются (cutout). **Полупрозрачности в 3D нет.** Стёкла и частицы
  делай cutout-текстурами или 2D-слоем поверх.

### 4.7 Свет, небо, туман

- Источники света:
  - `newLightSource(name, "point", x, y, z, colorInt, intensity, radius)`;
  - `newLightSource(name, "directional", dirX, dirY, dirZ, colorInt, intensity)`;
  - `newLightSource(name, "spot", x, y, z, dirX, dirY, dirZ, angle, radius, colorInt, intensity)`.
  Через Lua — `A(name, "LightSource")` плюс `lightsource.*`.
- В `gpu-z` попиксельно считаются **не больше 4 источников**: directional всегда, остальные выбираются по
  близости к камере. В `sorted` свет повершинный.
- Окружение: `setHemisphereAmbient(sky, ground, intensity)`, либо прямо `R.ambientSky = {r,g,b}`,
  `R.ambientGround`, `R.ambientIntensity` с `R.ambientRevision = (R.ambientRevision or 0) + 1`.
- После прямой правки `R.lights` увеличивай `R.lightRevision`.
- `setSkybox("skybox_0", exposure, true)` — небо. При `syncLighting = true` добавляется солнце и подстраивается
  ambient.
- Тумана нет. Дальность режется `renderDistanceSq`.

### 4.8 Бэкенды рендера и бюджет

- **`gpu-z`** — основной. Глубина хранится в цветовом буфере, сравнение идёт через
  `GL_*_shader_framebuffer_fetch` (Mali, Adreno, PowerVR, Apple). Каждый меш — нативный `display.newMesh`, свет
  попиксельный, сортировка не нужна. Для фона создаётся чёрный прямоугольник `S.cc3dZBackground`.
- **`sorted`** (painter) — запасной вариант без framebuffer fetch: треугольники сортируются на CPU каждый кадр,
  есть клиппинг по near, свет повершинный. Бюджет **≈ 1–3 тыс. треугольников в кадре**.
- Проверка бэкенда: `R.backend`, `R.backendInfo`. Цифра на экране — Script2 при `showDebug = true`.
- Советы по производительности:
  - Меньше объектов: статичную геометрию объединяй в один меш, `subMeshes` по материалам.
  - Каждый `MeshRenderer` — это нативный объект Solar2D.
  - Не меняй `Transform` без надобности: матрицы пересчитываются по ревизиям.
  - Не создавай и не удаляй объекты каждый кадр, держи пул.
  - Объекты за `renderDistance` и вне пирамиды видимости отсекаются по `bounds.r`.

### 4.9 Физика (Script20)

- Тело = `PhysicsBody` (`bodyType`: `dynamic`, `static` или `kinematic`) + коллайдеры `Box`, `Sphere`, `Capsule`.
  Объект только с коллайдером ведёт себя как статичный.
- **Размеры коллайдеров умножаются на масштаб объекта.** `BoxCollider.size` — полный размер: `size × scale`.
  Для `builtin:cube` со scale `s` ставь `size = 2`. Для `builtin:sphere` — `radius = 1`.
  Для `builtin:capsule` подходят значения по умолчанию (`radius 0.5`, `height 2`).
- Силы:
  - `PhysicsAddForce(name, x, y, z, mode)`, где `mode`: `force`, `impulse`, `velocity`, `velocitychange` или
    `acceleration`;
  - `PhysicsAddTorque(name, x, y, z, mode)`;
  - `PhysicsExplosion(x, y, z, radius, force, upBias)`.
  Lua-аналоги — `E.SBOX3D_PHYS_ADDFORCE`, `E.SBOX3D_PHYS_ADDTORQUE`, `E.SBOX3D_PHYS_EXPLODE`.
  Можно и напрямую: `pb.velocity.x = ...`.
- Гравитация и настройки: `PhysicsSetGravity(x, y, z)`; `PhysicsTune(key, value)` — `fixedDelta` (1/60),
  `maxSubSteps` (4), `velocityIterations`, `sleepThreshold`, `timeScale`, `frictionCombine`… Шаг фиксированный
  внутри `GAME_conditions`.
- Рейкаст:
  ```lua
  local name, dist, x, y, z, nx, ny, nz = E.SBOX3D_RAYCAST(ox, oy, oz, dx, dy, dz, maxDist, ignoreName, ignoreDynamic)
  ```
  Блочный вариант `PhysicsRaycast(...)` пишет результат в `rayHit`, `rayDist`, `rayX..Z`, `rayNX..NZ`.
- События кадра (только чтение) **(наблюдение)**:
  - `R.physicsContactEvents[1..R.physicsContactEventCount]` — `{a, b, impulse, x, y, z, nx, ny, nz}` для
    ударов с импульсом больше `eventImpulseThreshold` (0.5);
  - `R.physicsTriggerEvents[1..R.physicsTriggerEventCount]` — `{a, b}` для пересечений с коллайдерами
    `isTrigger = true`.

  Это подходит для подбора монет, зон финиша, урона от удара.
- Сон: тела засыпают после `sleepTime`. Двигаешь вручную — буди.

### 4.10 Игрок

- **Встроенный FPS-игрок (Script21 + Script4)**. Работает сразу: сенсорный стик и кнопки → `inMoveX/inMoveZ`,
  `yaw/pitch`, `inJump`… → `PlayerController` на объекте `Player` → камера.
  - Параметры — переменные сцены Script21: `spawnX/Y/Z`, `moveSpeed`, `jumpHeight`, `standHeight`, `eyeHeight`,
    `reach`, `throwForce`…
  - «USE» берёт предметы с тегом `grabbable`. По `explosive` вызывается взрыв, по `button` пишется
    `R.playerPressed = <имя>`.
  - Состояние читай из `E.G_varsP.playerState/playerGrounded/playerSpeed` или через
    `E.SBOX3D_PLAYER_STATE("Player")` → `grounded, state, speed, eyeX, eyeY, eyeZ, vy, groundName`.
  - Телепорт: `E.SBOX3D_PLAYER_TELEPORT("Player", x, y, z)`.
- **Свой контроллер или другая камера** (гонка, вид сверху, третье лицо):
  - Отключи встроенного игрока: в самом раннем `onStart` поставь `R._playerReady = true`. Script21 проверяет
    этот флаг и выходит.
  - Отключи UI: `E.GAME_conditions.cc3dUiBuilt = true`. Script4 смотрит этот флаг. Если UI уже создан,
    удали `E.SBOX3D_UI_GROUP`.
  - Камеру ставь сам каждый кадр через `camX/camY/camZ/yaw/pitch`.
  - Свой PlayerController на любом объекте: `A(name, "PlayerController")` и каждый кадр
    `E.SBOX3D_PLAYER_INPUT(name, forward, strafe, yawDeg, jump, sprint, crouch)`.

### 4.11 2D поверх 3D (HUD, меню)

- Создавай свои группы в stage **после** корня SboxB (`stage:insert(group)`), при необходимости `group:toFront()`.
- Координаты 2D: `display.screenOriginX/Y`, `actualContentWidth/Height`.
- Текст — `display.newText`, полоски — `display.newRect`. Картинки — `display.newImageRect` из
  `E.G_other.getImage(name)` с `system.DocumentsDirectory`.
- Касания по HUD возвращай `true`, чтобы они не уходили в стик и взгляд Script4. Script4 ловит касания на всём
  экране.

### 4.12 Минимальный пример: арена с ящиками и счётом

Lua-модуль, один скрипт `requestApi` (до минификации):

```lua
local D = print5("debug") local E = D.getfenv(print5)
local G = { score = 0 }
E.ARENA = G
local tries = 0
local function findSbox()
  local s = display["get" .. "CurrentStage"]()
  for i = 1, s.numChildren do local g = s[i] if g and g.objects and g.objects3d then return g.objects3d.cc3dV2, s end end
end
local function boot()
  tries = tries + 1
  local R, stage = findSbox()
  if not (R and R.ready and R.physicsReady and E.SBOX3D_NEW and R.playerReady) then
    if tries < 600 then E.timer.performWithDelay(16, boot) end
    return
  end
  local N, A, X = E.SBOX3D_NEW, E.SBOX3D_ADD, E.SBOX3D_EDIT
  local function box(name, x, y, z, sx, sy, sz, tex, mass)
    N(name, x, y, z)
    A(name, "MeshFilter") X(name, "meshfilter.mesh", "builtin:cube")
    A(name, "MeshRenderer") X(name, "meshrenderer.texture", tex)
    X(name, "scalex", sx) X(name, "scaley", sy) X(name, "scalez", sz)
    A(name, "BoxCollider")
    X(name, "boxcollider.size.x", 2) X(name, "boxcollider.size.y", 2) X(name, "boxcollider.size.z", 2)
    if mass then A(name, "PhysicsBody") X(name, "physicsbody.mass", mass) X(name, "tag", "grabbable") end
  end
  box("Floor", 0, -0.5, 0, 20, 0.5, 20, "stone")            -- статичный пол 40x1x40
  for i = 1, 6 do box("Crate" .. i, (i - 3.5) * 2, 1 + i, 6, 0.5, 0.5, 0.5, "stone", 10) end
  -- монета-триггер
  N("Coin", 0, 1, 10)
  A("Coin", "MeshFilter") X("Coin", "meshfilter.mesh", "builtin:sphere")
  A("Coin", "MeshRenderer") X("Coin", "meshrenderer.texture", "stone")
  X("Coin", "size", 0.3)
  A("Coin", "SphereCollider") X("Coin", "spherecollider.radius", 1) X("Coin", "spherecollider.istrigger", true)
  -- свет: блок-функция newLightSource или компонент напрямую
  A("Sun", "LightSource") X("Sun", "lightsource.type", "directional")
  X("Sun", "lightsource.dirX", 0.4) X("Sun", "lightsource.dirY", -1) X("Sun", "lightsource.dirZ", 0.3)
  X("Sun", "lightsource.intensity", 1)
  -- HUD
  local hud = E.display.newGroup() stage:insert(hud)
  local t = E.display.newText({ parent = hud, text = "0", x = E.display.contentCenterX, y = 30, font = E.native.systemFontBold, fontSize = 28 })
  local coin = R.gameObjects["go-Coin"]
  local spin = 0
  local function tick()
    spin = spin + 3
    coin.components.Transform.rotation.y = spin                 -- градусы
    for i = 1, (R.physicsTriggerEventCount or 0) do
      local ev = R.physicsTriggerEvents[i]
      if (ev.a == "Coin" or ev.b == "Coin") and (ev.a == "Player" or ev.b == "Player") then
        G.score = G.score + 1
        t.text = tostring(G.score)
        X("Coin", "x", E.math.random(-15, 15)) X("Coin", "z", E.math.random(-15, 15))
      end
    end
  end
  table.insert(E.GAME_conditions, tick)
end
E.timer.performWithDelay(1, boot)
```

Добавь скрипт: `python3 tools/pack_sobixel.py script proj/ 23 "Arena" arena.lua`. Демо-сцену из Script5 при этом
удали или замени, у неё те же имена объектов (`Floor`).
Точка появления игрока — переменные сцены `spawnX/spawnY/spawnZ` в Script21 (по умолчанию 0, 3, 0).

---

## 5. Когда SboxB не подходит

Если нужен свой мир (BSP-уровни, тысячи треугольников статики, скелетная анимация), можно оставить от SboxB
**только Script1 (Renderer)**. Он даёт шейдеры глубины (`R.effect` / `R.zEffect`, `R.shell`), бэкенд и чёрный фон.
Рисуй своими мешами `display.newMesh{hasZ = true}` в группе корня с эффектом `R.zEffect` и своими uniform-ами:
- `mv` — матрица вида-модели 4×4 по столбцам;
- `nm` — матрица нормалей; в `nm[4]`, `nm[8]`, `nm[12]` лежит ambient;
- `lightP` / `lightC` — до 4 источников.

Встроенного игрока и UI SboxB тогда гаси, как в разделе 4.10.

---

## 6. Тестирование без телефона

- Каждый Lua-модуль прогоняй через `tools/luamin.py`. Он ловит все запреты раздела 3.2 и синтаксис (`luac5.1`).
- Логику проверяй в обычном `lua5.1` с маленьким моком окружения:
  - `print5 = function() return debug end`;
  - таблица `E` с `display` (группы и `newMesh`, которые просто запоминают поля), `timer.performWithDelay`
    (очередь), `system.getTimer`, `GAME_conditions`, `G_varsP/G_varsS/G_tablesE`;
  - цикл, который вызывает функции из `GAME_conditions` и срабатывающие таймеры.

  Для SboxB-логики мок подставляет `R = {ready = true, physicsReady = true, gameObjects = {}, meshAssets = {}}` и
  заглушки `E.SBOX3D_NEW/ADD/EDIT`.
- После упаковки распакуй `.sobixel` обратно (`pack_sobixel.py unpack`) и прогони скрипты оттуда. Это лучшая
  проверка, что упаковка не испортила код.
- На устройстве ошибки видны через `Runtime` `unhandledError` (`ev.errorMessage`, `ev.stackTrace`). Выводи их
  в свой HUD или консоль.

---

## 7. Частые ошибки

| Симптом | Причина |
|---|---|
| Скрипт «молча» не работает | в тексте `\`, `--`, `[[`, перевод строки, `getCurrentStage` или `pcall(function`. Прогони валидатор |
| `attempt to call global 'SAFE_RUN'` | `pcall(function ...)` в тексте |
| `function at line N has more than 200 local variables` / `upvalues` | слишком большой модуль в одной функции. Группируй локальные в таблицы, дели модуль |
| Объект не виден | нет `MeshRenderer` или текстуры (`materials[1].link == nil` → меш скрыт); не выставлен `dirty`; объект за `renderDistanceSq`; неверный порядок индексов |
| Ящик проваливается или висит в воздухе | коллайдер не совпадает с мешем (`builtin:cube` → `size = 2`) или тело спит после ручного перемещения |
| Камера «не туда» | углы в радианах вместо градусов, или забыт `R.eulerScale` |
| Встроенный игрок мешает своей камере | не выставлен `R._playerReady = true` до старта Script21 |
| Всё дёргается на слабом телефоне | бэкенд `sorted` и много треугольников. Объединяй меши, уменьшай `renderDistanceSq` |
| После перезапуска сцены всё двоится | не сняты слушатели и группы прошлого запуска (раздел 3.4) |
