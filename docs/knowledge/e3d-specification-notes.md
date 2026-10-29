# PDMS 資料から整理した E3D 開発用仕様メモ

整理日: 2026-10-16。対象ツールは AVEVA E3D 4.0 向け。根拠はユーザー提示の PDMS/PARAGON 資料と会話です。実機確認済みの E3D 仕様書ではありません。[未確認事項](open-questions.md)を併読してください。

## 1. コマンド表記・式・数値・単位

出典: Command Parts とその前後の構文説明、会話継承、第4章 4.7.5、第5章 5.3。

- コマンド表記の大文字部分は最小略記。小文字の後半は省略でき、途中までの入力も可能。入力自体は大文字・小文字を区別しない。全大文字の語をさらに短縮できるとは限らない。
- 構文図の `<...>` は参照先や引数の種類で、入力する文字列ではない。分岐は選択肢、迂回路は省略可能な経路、反復路は複数指定を表す。
- `integer` と一般の数値を区別する。`word` は PDMS の短い語で、一般説明では最大4文字。自由文字列の `text` と別型。
- text は空白を含められ、`'...'` または `|...|` で区切る。表示用の曲がった引用符を構文として使わない。
- 名前は通常 `/` で始まる。マクロ変数は `!` で始まる。
- コマンドの連結にカンマを使う説明がある。一方、提示例には空白で連続する属性代入もあるため、単純に1行1属性と仮定しない。
- `<eval>` は括弧で囲んだ式の評価。実行時に計算して値を代入する式と、カタログ形状に保存して部品ごとに評価する PARAM 式を区別する。
- 数学・論理・文字列の式が使われる。一般の式の詳細は別のカスタマイズ資料が参照されており、写真だけでは全構文を確定できない。
- 数値表記には `5.5 EX 3` のような指数表現、`5.3/4` のような帯分数がある。後者は5.75を表す説明。
- 通常入力の単位省略は現在の作業単位。明示単位で上書きできる。フィート・インチの短縮入力には FINCH 設定などの条件があるため、どの入力でも有効とはしない。
- 表示丸めと保存精度は別。PRECISION は出力精度に関する設定として扱う。
- **形状の PARAM 式をシステムが評価する際は作業単位を停止し、DB 単位を使う。距離の DB 単位は mm。** この文脈の裸の `+3` は3 mm。3 inchにしたい場合は単位を明示する。
- 「通常入力時の作業単位」と「保存された形状式の評価時の DB 単位」を同じ規則にしない。

## 2. 識別子・ナビゲーション・基本操作

出典: Command Parts、Specific Element Identifier、Cursor-picking Identifier、第5章 5.1。

| 指定 | 資料での意味 |
| --- | --- |
| `/名前` | 名前による要素指定 |
| SAME | 直前にアクセスした要素 |
| OWN / OWNER | 現在要素の所有者 |
| NEXT 2 | 同じ階層のメンバー順で2つ先 |
| 数字だけ | 現在要素の該当順番のメンバー |
| LAST 3 MEM | 現在要素の末尾から3番目のメンバー |
| END | 現在要素から階層を1段上がる |
| SECT | 現在要素の上位にある Section |
| CATE 3 | Category の順番指定の例 |
| GOTO PTREF | 参照属性の参照先へ移動 |
| ID @ | カーソルがヒットした最下位要素 |
| ID SBOX @ / ID SCOM @ | 型を限定したカーソル選択 |

- CE、OLD も基本参照コマンドとして列挙される。ただし OLD の正確な動作は提示部分だけでは確定していない。
- FIRST / LAST / NEXT / PREVIOUS と、要素型を付ける指定例がある。移動の全条件は未確認。
- **メンバー順番号と、P-point の NUMB は別概念。** NAREF の数値指定は前者。
- END は階層移動だけでなく ALPHA の終了等にも現れる。コマンド文脈で解釈する。
- QUERY、NEW、DELETE、REORDER、COPY、RENAME、INCLUDE が基本操作。
- REORDER はメンバー順変更。INCLUDE は既存要素をメンバー構成へ組み込む操作の例で、ファイル読み込みの include と決めつけない。COPY / INCLUDE の完全な所有・参照・複製規則は未確認。
- NAME / UNNAME、LOCK / UNLOCK がある。PDMS には名前なし要素も存在する。ツールの表示名ルールとは区別し、内部識別を名前だけに依存させない。
- コマンドが作用する要素はカタログ DB の階層。DESIGN の SITE 等の操作をそのまま PARAGON に流用しない。

## 3. 要素型と別名

出典: Catalogue Element Types の一覧、第4章の階層図、会話継承。

問い合わせの型表示は通常4文字。説明やコマンドでは長い名称も使われる。以下は資料に現れた表記をまとめたもので、任意の型名を機械的に4文字へ切ればよいという意味ではない。

| 分類 | 資料で確認した要素・表記 |
| --- | --- |
| 部品 | SCOM / COMP、SPRF / PROF、SJOI / JOIN、SFIT / FITT |
| 正の3D形状 | SBOX、BOXI、LSNO、SCON、SSPH、LCYL、SCYL、SSLC、SCTO、SRTO、TUBE、LPYR、SDIS、SDSH、LINE、SEXT、SREV |
| 3D形状集合 | GMSET / GMSE |
| 負の3D形状集合 | NGMSET / NGMS |
| 負形状 | NSBO、NSCO、NLSN、NSDS、NSSL、NSSP、NLCY、NSCY、NSCT、NSRE、NSRT、NLPY、NSEX 等 |
| 輪郭 | SLOOP / SLOO、SVERTEX / SVER |
| 構造断面 | GMSSET / GMSS、SRECTANGLE / SREC、SANNULUS / SANN、SPROFILE / SPRO、SPVERTEX / SPVE |
| 3D Pointset | PTSET / PTSE、PTAXI / PTAX、PTCAR / PTCA、PTMIX / PTMI |
| その他の点型 | PTPOS（会話で扱った追加型。今回の3型の説明から削除しない） |
| 構造 Pointset | PTSSET / PTSS、PLINE / PLIN |
| Dataset | DTSET / DTSE、DATA |
| 詳細・材質文 | SDTEXT / SDTE と DTEXT / DTEX、SMTEXT / SMTE と MTEXT / MTEX |
| ボルト表 | BLTABLE / BLTA、BLIST / BLIS、SBOLT / SBOL、LTABLE / LTAB、MBOLT / MBOL、MBLIST / MBLI、DTABLE / DTAB |
| 接続表 | CCTABLE / CCTA、COCO、COCDES / COCODES |
| 単位 | UNIT、MSET、MTYPE / MTYP、ATLIST / ATLI、USECTION / USEC、UDEFINITION / UDEF |
| Group | GPWL、GROUP / GROU |
| Part | PRTWLD、PRTELE、GPART |
| Specification | SPWL、SPEC、SELEC / SELE、SPCOM / SPCO |
| Table World | TABWLD、BRTAB、NOMTAB、WTHTAB、PDATAB とその下位要素 |

- 型一覧で Fitting は `SFITting`。`FITTing number` は無効と注記されている。説明上の別名と入力できるコマンドを同一視しない。
- 負の皿形状 NSDS は写真に存在する。初期のツール要素一覧に欠けている可能性があり、追加候補。
- 表の長名称の最小略記は元の大小文字表記で個別確認する。上記大文字化は検索用の整理であり、最小略記の仕様ではない。

## 4. 共通コマンド・色

出典: 第3章 3.1–3.6 と COLOUR の構文・色表。

### 4.1 モジュール・保存・終了・ログ

- PARAGON は PROPCON のコマンドを含む。SPECONMODE で SPECON コマンドへ入り、EXIT でそのモードを抜ける。
- SAVEWORK は前回の保存以降の変更を DB に保存する。GETWORK は他者による READ / Multiwrite DB の変更を取り込む。
- SAVEWORK / GETWORK に DB 番号を指定できる。番号は STATUS に出る現在の MDB 内の並び。省略は MDB 全体。
- GETWORK は DB 再読み込みの負荷がある。資料では必要な変更を取得する場合の利用が勧められる。
- QUIT は前回 SAVEWORK・モジュール変更・MDB変更以降の未保存変更を破棄して終了する説明。表示設定も保存しない。
- QUIT のモジュール指定、QUIT FINISH による PDMS 終了がある。
- ALPHA LOG は COMMANDS、REQUESTS、または両方のログ。ALPHA FILE は REQUESTS だけ。OVERWRITE / APPEND が使える。
- ログ先を開いた後は画面とファイルへ出力し、END またはモジュール変更で終了する。通常の階層移動 END と区別する。
- TRACE ON/OFF は TTY での自動属性表示を制御。マクロ実行中は自動でOFF。

### 4.2 色の定義・用途

- COLOUR の対象は色番号、ACTIVE、CE、VISIBLE。色名、または MIX RED / GREEN / BLUE で指定する。
- RGB は各0–100の整数。3成分を所定順で全て指定し、合計100にする必要はない。
- 100個のユーザー定義色がある。番号の色を再定義できるため、番号だけで恒久的な RGB を固定しない。
- ACTIVE は作業対象の significant component の色。現在要素がプリミティブなら、そのプリミティブ以外の同部品の形状に使用。
- CE は現在選択中の要素、VISIBLE はその他の表示要素。Active と Visible の要素で Draw List を構成する説明。
- CE の既定は yellow、VISIBLE は lightgrey。
- 色番号1–16の既定は順に grey、red、orange、yellow、green、cyan、blue、violet、brown、white、pink、mauve、turquoise、indigo、black、magenta。
- `Q COLOUR` で対象の色を問い合わせる。色設定は表示情報であり、部品の寸法データではない。
- 同じ英語色名でも Web/CSS の RGB と一致するとは限らない。

資料の色表（0–100 の RGB 値）:

| 色名 | R | G | B |
| --- | ---: | ---: | ---: |
| black | 0 | 0 | 0 |
| white | 100 | 100 | 100 |
| whitesmoke | 96 | 96 | 96 |
| ivory | 93 | 93 | 88 |
| grey | 66 | 66 | 66 |
| lightgrey | 75 | 75 | 75 |
| darkgrey | 32 | 55 | 55 |
| darkslate | 18 | 31 | 31 |
| red | 80 | 0 | 0 |
| brightred | 100 | 0 | 0 |
| coralred | 80 | 36 | 27 |
| tomato | 100 | 39 | 28 |
| plum | 55 | 40 | 55 |
| deeppink | 93 | 7 | 54 |
| pink | 80 | 57 | 62 |
| salmon | 98 | 50 | 44 |
| orange | 93 | 60 | 0 |
| brightorange | 100 | 65 | 0 |
| orangered | 100 | 50 | 0 |
| maroon | 56 | 14 | 42 |
| yellow | 80 | 80 | 0 |
| gold | 93 | 79 | 20 |
| lightyellow | 93 | 93 | 82 |
| lightgold | 93 | 91 | 67 |
| yellowgreen | 60 | 80 | 20 |
| springgreen | 0 | 100 | 50 |
| green | 0 | 80 | 0 |
| forestgreen | 14 | 56 | 14 |
| darkgreen | 18 | 31 | 18 |
| cyan | 0 | 93 | 93 |
| turquoise | 0 | 75 | 80 |
| aquamarine | 46 | 93 | 78 |
| blue | 0 | 0 | 80 |
| royalblue | 28 | 46 | 100 |
| navyblue | 0 | 0 | 50 |
| powderblue | 69 | 88 | 90 |
| midnight | 18 | 18 | 31 |
| steelblue | 28 | 51 | 71 |
| indigo | 20 | 0 | 40 |
| mauve | 40 | 0 | 60 |
| violet | 93 | 51 | 93 |
| magenta | 87 | 0 | 87 |
| beige | 96 | 96 | 86 |
| wheat | 96 | 87 | 70 |
| tan | 86 | 58 | 44 |
| sandybrown | 96 | 65 | 37 |
| brown | 80 | 17 | 17 |
| khaki | 62 | 62 | 37 |
| chocolate | 93 | 46 | 13 |
| darkbrown | 55 | 27 | 8 |

## 5. カタログ階層と参照

出典: 第4章 4.1–4.6、4.8–4.10、階層図。

- CATA がカタログの最上位。配管 Section は SECT、構造 Section は STSEC。Section は必須。
- 配管 Category は CATE、構造 Category は STCA。Category は任意で、Section が直接そのメンバーを所有できる。
- 共通属性は TYPE / NAME / OWNER / LOCK。UDA と UDET を使える。認識していない属性や要素を消さず保持する。
- CATA の主属性は DESC、PURP、CSTA。PURP は利用する Specification と同じ用途語（PIPE、FITT 等）に合わせる説明。
- Section の主属性は DESC、PURP、GTYP。GTYP は DESIGN の汎用型（VALV、BEAM 等）に合わせる。
- Category は DESC、PURP、GTYP、SKEY と、PTRE / GMRE / DTRE / CDET などの参照を持つ。
- **Category の PURP は対応する Specification の STYPE に合わせる説明**（GATE、GLOB 等）。CATA の PURP の規則と混同しない。
- SPEC から参照するカタログ要素は CATA 配下に存在する必要がある。一方、SPEC に未登録のカタログ要素も存在できる。
- WORLD 直下には CATA 以外に UNIT、接続表、ボルト表、SPWL、GPWL、TABWLD、PRTWLD 等の階層がある。
- 設計要素の SPREF は Specification の SPCOM を参照し、SPCOM の CATREF がカタログ部品を参照する。
- 詳細文の参照には図の DETAI、別の説明の DETREF が現れる。正確な属性別名の対応は未確認。
- カタログ部品はメンバーを持たない。PTSET / GMSET は部品の子として作るのではなく、別の要素として作って参照する。
- 1つの定義を多数の部品・設計で共用する。カタログは会社共通にも、プロジェクトで必要な範囲だけにも構成できる。
- TEXT は汎用情報で階層の複数位置に置ける。詳細文 DTEX / SDTE、材質文 MTEX / SMTE と役割が異なる。
- DTSET は DATA をまとめ、断面積など、その他の場所にない部品データ・計算データを保持する。
- SDTE / SMTE は Specification 側からも参照される。
- 通常の GMSET に加え、構造用の GMSSET、負形状用の NGMSET がある。
- **負の3Dプリミティブは、正の3Dプリミティブの子としても所有できる**との階層図の注記。
- SEXT / SREV と負形状の対応型は SLOO を持ち、SLOO が SVER を持つ。構造用 SPRO は SPVE を持つ。

### 5.1 部品クラスと主な属性

| クラス | 主な参照・属性 |
| --- | --- |
| SCOM / COMP | PTREF、GMREF、PARAM、GTYPE、DTREF |
| SPRF / PROF | PSTREF（PTSSET）、GSTREF（GMSSET）、PARAM、GTYPE、DTREF |
| SJOI / JOIN | PSTREF、PTREF、GMREF、PARAM、GTYPE、CTYA、CTYO、DTREF |
| SFIT / FITT | PTREF、GMREF、PARAM、GTYPE、CTYA、DTREF |

- Profile は断面を定義し、設計時に長さを与えて Section になる。
- Joint は Section 同士をつなぐ構造部品。構造 Pointset と3D Pointset を使用する。
- Fitting は Section に付属する部品で、例としてハンガー取付。参照属性一覧では構造 Pointset の参照はない。PARAM説明文だけ構造 Pointset に言及する矛盾あり。
- PARAM以外の部品属性は実際の語または要素参照を設定する。部品属性自体を PARAM 式で定義しない。Pointset / Geomset の属性はパラメータ化できる。
- 参照は通常名前で設定するが、階層とメンバー順を組み合わせた一般識別子でも指定できる。
- Joint の CTYA は Attached Section 側の接続型。設計選択時に相手の CTYS / CTYE が未設定なら初期化し、整合性検査で照合する。
- CTYO は Owning Section 側で、Secondary Joint に使用。
- Fitting の CTYA はパイプハンガーの場合の接続型。相手の HCON / TCON の初期化と照合に使用。

SCOM の GTYPE は分岐整合性検査に必要な列挙値として説明される:

`ATTA BEND CAP CLOS COUP CROS DUCT ELBO FBLI FILT FLAN/FLG FTUB GASK HELE INST INSU LJSE NOZZ OLET PCOM REDU SHU TEE TRAC TRAP TUBE UNIO VALV VENT VFWA VTWA WELD`

- TUBE は暗黙チューブ、FTUB は固定長チューブ。
- Profile の GTYPE は任意の word。推奨例は BEAM、BRAC、COLU、GANT、GIRD、JOIS、PILE、PROF、PURL、RIDG、SDRA。
- Joint も任意の word で、BASE、JOIN、KNEE が例。
- Fitting も任意の word で、FITT が推奨。

### 5.2 Part と選択テーブル

- GPART は SPCO 相当の CATREF / DETREF / MATXT / CMPREF / BLTREF 等と追加プロパティを持ち、部品の情報をまとめる。Specification なしでも利用できる構成。
- PRTWLD の下に PRTELE による任意段数の分類と GPART。別の全体図には PRTWLD 直下の GPART もある。
- 選択テーブルは SPWL → TABGRO → CTABLE。CTABLE は1つの TABHEA と多数の TABITE を持つ。
- TABHEA は選択質問（TABHQU）を定義し、TABITE は Part 参照と回答を持つ。図に TABQUE（item answer）があるが、親子線が明瞭でないため細部は要確認。
- 選択方法は設計文脈による criteria、属性フィルタ、両方。カタログを直接フィルタ検索する方法もある。
- プロジェクトで許可する部品の部分集合を提供する場合は選択テーブルが推奨。
- 選択テーブルでの Part 利用は配管以外の discipline が対象と説明。配管では SPCO と同様に Piping Specification に Part を追加できる。

## 6. PARAM・単位・登録と変更

出典: 第4章 4.7–4.8、第5章 5.2–5.4、第6章 MODEL SETTINGS。

### 6.1 パラメータの参照元

| 表記 | 参照元 |
| --- | --- |
| PARAM n | カタログ部品自身の PARAM[n] |
| IPARAM n | 対応する保温部品の PARAM[n] |
| APARAM n | Attached Section のカタログ部品 PARAM[n] |
| OPARAM n | Owning Section のカタログ部品 PARAM[n] |
| DES PARAM n | 自身を参照する設計要素の Design Parameter Array[n] |
| DES APARAM n | Attached Section の設計要素の配列[n] |
| DES OPARAM n | Owning Section の設計要素の配列[n] |

- 通常部品への SPREF と、保温仕様への ISPEC は別参照。MODEL SETTINGS の保温指定は INSPEC 表記であり、属性名・コマンド文脈を区別する。
- この資料で設計要素の Design Parameter Array は10値。
- PARAM / IPARAM / DES PARAM は配管部品、Profile、Primary/Secondary Joint、Fittingで利用可能。
- APARAM / DES APARAM は Primary と Secondary Joint。OPARAM / DES OPARAM は Secondary Joint と Fitting。
- Primary Joint は Attached Section、Secondary Joint は Attached と Owning Section、Fitting は Owning Section を持つ。
- 構造パラメータは Profile 自体には意味を持たない。同じ Joint カタログ型でも設計側での使われ方で参照文脈が変わる。
- PARA、IPARA、APARA、OPARA や DESP / ADESP / ODESP 等の表記が式例に現れる。許可略記は構文の確認が必要。
- 同じ番号でも family ごとに参照元・意味が異なる。IPARAM等に自身の PARAM 値や役割名を流用しない。

### 6.2 値・式・次元

- コンポーネント PARAM の入力は数値・式・word。保温・構造・Design DB パラメータは数値または式との説明。
- 入力式が実行時に評価されるのか、式のまま残るのかは該当構文ごとに確認する。全 PARAM 式を無条件に遅延保存としない。
- パラメータはサイズ・形状・接続型などのために使うが、通常は番号・個数・意味をユーザーが設計する。全機種共通の PARAM 番号規則はない。
- 単位付き値は DB 単位に変換され、通常のカタログ・設計パラメータでは物理次元も保持する。NONE / DIST / ANGL 等を区別し、再定義で次元も変わる。
- 異なる物理次元の加算、角度でない値への三角関数、長さ属性への不適合な代入等は警告・エラーの対象。ただし写真の例に添字の矛盾がある。
- TAN / SIN や逆三角関数 ATAN / ASIN、四則演算、単項マイナス、属性 ANGL / HEIG 等の参照例がある。ANGL は角度、HEIG は距離。
- 形状評価では DB 距離単位 mm。明示単位の推奨と作業単位の規則は第1節を参照。

### 6.3 登録・変更時の注意

- NEW で CATA、SECT / STSEC、CATE / STCAT、SCOM / SPRF / SJOI / SFIT 等を作る。
- 名前や PARAM がまだない部品も作成可能。
- PTREF / GMREF に参照先を設定する時点で、対象の PTSET / GMSET が既に存在する必要がある。
- **`PARAM v1 v2 ...` は配列全体の置換。短い一覧を設定すると末尾の既存値が消える。**
- **`PARAM[n] value` は既に設定された項目の変更用。未設定の配列をこの構文だけで拡張できるとは扱わない。**
- QUERY ATTRIBUTES、QUERY PARAMETERS、QUERY PARAMETER[n] が問い合わせの例。
- 参照されている部品を削除すると参照を失う。編集時に削除・再作成して同名だから安全と判断しない。
- MODEL SETTINGS の PARAM 既定値や他 family の specimen 値は現在の PARAGON セッション用。カタログ DB の実部品値ではない。

### 6.4 特例と資料のパラメータ例

- **GTYPE=TUBE かつ GMSET がない暗黙チューブでは PARAM2 が外径。保温する場合の IPARAM1 は保温厚さの2倍。** 全配管部品への共通ルールに拡張しない。
- 保温なしのとき IPARAM は0になる説明。参照文脈が不明で値を得られない場合と、明示的に保温なしの場合を区別する。
- 保温は既存プリミティブへの加算、または別プリミティブで表現できる。保温なしで直径0・長さ非0になる形状も説明される。
- Slip-on flange の例は、P1=呼び径、P2=外径、P3=厚さ、P4/P5=両接続点の接続型。
- Reducing tee の例は、P1/P3=主・分岐呼び径、P2/P4=主・分岐外径、P5=主配管全長の半分、P6=分岐突出長、P7/P8=主・分岐接続型、P9/P11=主・分岐フランジ外径、P10/P12=同厚さ。溶接形は1–8、フランジ形は全12の利用例。
- Angle joint の例は、自身の P1=脚高さ、P2=足長さ、P3=板厚。Attached 側 A1=断面高さ、A2=フランジ幅。
- 以上は各例の規則。一般的な E3D 標準番号表として固定しない。原図・固有名・マクロ一式は公開サンプルに転用しない。

## 7. 3D Pointset

出典: 第5章 5.5.1–5.5.11。PTPOS は以前の会話からの継承で、この写真列の3型と分ける。

| 型 | 位置 | 方向 |
| --- | --- | --- |
| PTAXI | PAXI 軸に沿う PDIS | PAXI |
| PTCAR | PX / PY / PZ | PTCDIR |
| PTMIX | PX / PY / PZ | PAXI |
| PTPOS（会話継承） | PTCPOS | PTCDIR / PTCD |

- NUMB は接続点番号。資料では NUMBER / NUM とも入力される。要素のメンバー順と区別する。
- PTAXI / PTMIX の PAXI は XYZ の基本軸、または XY / YZ / ZX 平面内の方向。5.5.5 の文章は XY のみと書くが、続く図には Z–X、Y–Z の例がある。
- 軸角度は数値、DDANGLE、パラメータ、TWICE a parameter で指定する説明。
- `Z 70 -X` のように、始点側の軸から指定側の軸へ回転する例がある。`X DDA Y` の DDA は DDANGLE 設計値を使う例として整理する。
- PAXI 未指定時は Y。PDIS 未指定時は0。PDISTANCE の最小略記は PDIS。
- PTCAR / PTMIX の各座標は個別に未指定なら0。パラメータや数式を使用できる。
- PTCDIRECTION の最小略記は PTCDIR。任意の1・2・3軸を任意順で指定でき、回転値は正・負・省略（0）に対応。式を含む方向指定例もある。
- PTCDIR 未指定時は Y。多軸の逐次回転の正確な解釈・U等の別軸表記は実機または方向構文全体で要確認。
- PTCAR は位置と方向を独立して指定する。PTAXI の軸に沿う位置決めと混同しない。
- 同じ PARAM を複数点が参照可能。異径ティーの主配管両端は同じ距離式と逆向きの軸を使用する例。
- 同じ分岐点を PTAXI と PTCAR のどちらでも定義できる例。
- PBOR は口径、PCON は接続型。配管部品で任意設定できる。Joint / Fitting では両者に意味がないと明記。
- PBORE / PCONNECTION / NUMBER の最小略記として PBOR / PCON / NUM が挙げられる。
- PBOR は数値式、PCON は BWD 等の語または PARAM による語の参照例。値型を一律数値にしない。
- PBOR と NUM は未指定時0。PCON の未指定時の正確な値は提示部分では不明。
- ツールでは P0 を自動の基準点として扱う決定があるが、実機コマンドの P0 の全仕様は今回の説明だけでは確定しない。

### 7.1 PSKEY と ISODRAFT

- 部品の SKEY は ISODRAFT の標準シンボルを定める。各 P-point の PSKEY は端部表現を追加する。
- 対応する語は BW（突合せ溶接）、CP（圧縮）、FL（フランジ）、SC（ねじ）、SW（ソケット溶接）、PL（プレーン）。
- PSKEY の既定は NULL。標準 SKEY の端部表現だけを使う。
- **PSKEY の効果は追加・重ね描き。標準の端部表現を置換するものではない。** 既に標準端部が描かれる場合は重複し得る。
- 主に独自シンボル等、端部表現がまだ定義されていない場合に使う説明。
- PSKEY は図面表現、PCON は接続条件。両者を同じ属性として扱わない。

## 8. Structural Pointset と P-line

出典: 第5章 5.6.1–5.6.6、第6章の P-line 表示。

- PTSSET は Profile / Joint の接続情報を持ち、PLINE を所有する。親に中立軸参照 NAREF を持つ。
- PLINE は PKEY、PLAXI、PX / PY、表示属性 LEVEL / CLFLA / TUFLA 等を持つ。
- PX / PY は断面内の位置。値またはパラメータ式。未指定の座標は0。
- PLAXI は方向文字、または XY 平面内の角度。数値・DDANGLE・パラメータ・TWICE を使う説明。未指定は Y。
- PKEY は点の NUMB に相当する識別用の word。**任意の word 値を使える**。TOS、BOS、NA / NAXI / ZAXI は代表例で、固定列挙ではない。
- NAREF は同じ PTSSET 内の P-line を名前またはメンバー順番号で指定する。数値3は3番目の P-line であり、P-point NUMB ではない。
- NAREF は明示推奨。未設定時の中立軸は、最初の PKEY=NA、なければ最初の NAXI、なければ最初の ZAXI の順。どれもなければ原点を通る＋Y方向と推定する。
- TOS / BOS を同じ全高 PARAM の正負半分で置く例がある。中立軸の P-line を作成後、親に戻って NAREF を設定する。
- 新規 PLINE の CLFLA / TUFLA は両方 FALSE。
- LEVEL は下限・上限の2整数。表示可否は LEVEL 範囲と描画フラグ、REPRESENTATION の組合せで決まる。

## 9. 3D Geomset と符号・干渉形状

出典: 第5章 5.7、第6章 6.3。プリミティブ固有属性の詳細は未提示部分もある。

- GMSET はプリミティブの集合で、寸法・配置・方向と干渉判定用形状を表す。
- プリミティブに OBST を設定し、描画には LEVEL / TUFLA / CLFLA も関係する。
- OBST=0 は干渉対象外、1はsoft、2はhard。障害物表示で1は破線、2は実線。
- 表示形状と干渉用包絡形状を別プリミティブで持たせる例がある。OBST>0だけで「通常表示しない」と判断できない。両方に使う形状もある。
- CLFLA は中心線モード、TUFLA はチューブモードの描画条件。モードによって別形状を描ける。
- **SCYL の PHEI は負の値を使う例がある。** PAXI の向きに配置した端から、負の高さで逆方向へ伸ばす。高さの符号を消したり、一律正値限定にしない。
- 点と形状が同じ PARAM を参照することで寸法を共有する例がある。実部品値による評価と、ツール独自の仮値編集は別層。
- 5.7 に「OBST が1または2の最初の20プリミティブだけを DESIGN の干渉チェックが使う」との旧資料上の制限。E3D 4.0 への適用は未確認。
- TVISIBLE / BVISIBLE の端面可視フラグは PARAGON では効果がないとの説明。E3D 全体でも無効とは断定しない。
- 会話継承: NAPP は Attached / Owner / Self に対する1 / 2 / 4の組合せ（0–7）として扱う。対象は設計文脈依存。
- 会話継承: LSNO / NLSN の上・下面で径／半径モード、LINE の順序付き P / T 点列（最大6）、SLINE の位置式、輪郭頂点の PRAD 等を管理する。これらの完全な実機構文は別途照合する。

## 10. MODEL と MODEL SETTINGS

出典: 第6章 6.1、6.4.1 とコマンド構文。

- MODEL は PARAGON の対話的な部品設計・表示を開始する。
- MODEL CE は現在の部品をビューへ追加する。資料の対象列挙は SCOM / SPRF / JOIN / SFIT。PTSET / GMSET 単体はこの方法では表示できない。
- MODEL END は設計を終了し、表示をクリアする。
- MODEL SETTINGS はコンポーネント PARAM の既定値、他 family の試用値、設計データ属性を設定する。
- 設計データに DDRADIUS / DDHEIGHT / DDANGLE があり、番号付き DES PARAM と別物。形状属性から直接参照する例もある。
- 当該説明では設定変更後に MODEL CE が必要。表示更新の記述は REPRESENTATION の別節と混ぜず整理する。
- 保温の選択には BORE / TEMP / PRESSURE を設定してから INSPEC を指定。表示側の保温設定も必要。
- MODEL SETTINGS DEFAULT は設計設定を初期化し、全 default/specimen パラメータを消して INSPEC も未設定にする。保存済み部品 PARAM 配列を消す説明ではない。
- QUERY MODEL SETTINGS で現在設定を問い合わせ、family または設計属性別にも絞れる。
- CAT（CATALOGUE）は PARAM / APARAM / OPARAM の非DES参照を明確にする任意指定。DES（DESIGN）で Design DB 側を指定する。IPARAM は別経路。
- 1行に異なる family の複数の番号・値を指定できる。値には ATAN / ASIN 等の式も使える。

### 10.1 既定値と単位の扱い

| 属性 | 資料の既定値 |
| --- | --- |
| TEMP | -100000（特殊値かは説明不足） |
| BORE | 150.0 mm |
| PRESSURE | 0.0 |
| DDANGLE | 90 degrees |
| DDHEIGHT | 100.0 mm |
| DDRADIUS | 225 mm |
| INSPEC | Nulref（未設定） |

- 設計データ属性は物理次元に合う単位を受け付け、式でも次元検査を行う。単位省略は現在の作業単位。
- **モデル用パラメータの試用値は、単位付き値を DB 単位に変換するが、物理次元自体は保持しない。** PARAGON 内の式評価ではそのモデルパラメータの次元検査をしない説明。
- 実カタログ・設計パラメータの次元保持とは異なる。DESIGN / DRAFT 等での式評価では次元検査が行われるとの説明。
- セッション用試用値と、本ツールが JSON に保持する無単位の共有仮PARAMは別仕様。

## 11. REPRESENTATION

出典: 第6章 6.2–6.4.8、末尾の colno 図。**同じ資料内に矛盾があるため、この節を単一の確定した実機動作として実装しない。**

### 11.1 プリミティブの表示条件

6.2–6.3 の説明では、LEVEL 範囲内で次の条件を OR で組み合わせる:

- TUBE ON かつ TUFLA=TRUE。
- CL ON かつ CLFLA=TRUE。
- OBSTRUCTIONS ON かつ OBST=1または2（GMSET）。

OFF はその経路を無効にする意味で、属性に該当する全形状を除外する意味ではない。OBST OFF でも TUFLA/CLFLA の条件で干渉用の皿形状が残る例がある。

- 表示設定は要素の保存属性を書き換えない。
- 6.3 は各経路が独立と説明し、TUBE / CL 両方ONの図もある。
- **6.4.2 は TUBE ON でCLが自動OFF（逆も同様）と記載。上記と不一致。**
- **6.4.5 は OBST ON が通常の LEVEL / TUBE / CL を上書きし、OBST>0を表示すると記載。6.3のLEVEL前提と不一致。**
- 障害物の線種は soft=破線、hard=実線。ただし複数表示経路が同時成立した場合の線種の優先順位は未確認。
- Profile は PROFILE と PROFILE CL を別に設定し、両方ONの例が明記される。PROF OBST / PROF INSU もある。
- INSU は保温の表示を切り替え、保温パラメータの影響を受ける形状を考慮する説明。保温部品の値と表示スイッチを区別する。

### 11.2 LEVEL と再描画

- REPR LEVEL の整数は共通値、PIPE / NOZZLE / STRUCTURE 付きで対象種別を指定できる。
- 基本的な描画対象判定は、表示LEVELがプリミティブのLEVEL範囲に入るかによる。OBSTの例外は矛盾として保留。
- LEVELが大きいほど詳細になるという固定ルールはない。資料の「1で詳細、3で簡略」はカタログの設定例。
- 6.4.4 の例では、設定後に Draw List に追加したものに適用し、既存の表示は変わらない。
- REPR UPDATE は変更を表示へ反映する。
- 一部参照節は Draw List から削除・再追加を要求する。一方6.3は REPRESENTATION 実行ごとに現在部品を再描画し、まとめて設定すると1回で済むと記載。適用文脈の差を要確認。
- Q REPR、Q REPR LEVEL、Q DISPLAY で表示設定等を問い合わせる説明。Q DISPLAY は単位・許容差・表示LEVELも含む。

### 11.3 P-point の表示

- 6.2.1 は PPOINTS ON が方向記号、OFFが点。完全に省略できないとの注記。
- 矢印長さの既定は50 mm。LENGTH 0も点になる。
- NUMBERS ON/OFFは記号の形と独立。文字SIZEの既定は5 mm。
- LENGTHとNUMBERSは同じコマンドで設定できる。6.4.6の部分構文にLENGTHがなくても、説明例と6.4.8全体構文にある。
- 6.4.6 は識別操作時に自動表示すると説明。
- **6.2.1と既定値一覧ではPPOINTS ON、6.4.6は既定OFFと記載。** 通常OFF時の残り方と識別時の挙動も実機照合が必要。
- Q REPR PPOINTSで問い合わせ。

### 11.4 P-line の表示

- 6.2.2 は PLINES ONで方向記号、OFFで点。PKEYS ON/OFFで識別語を別に切り替える。
- P-lineは描画属性の条件で完全に非表示にできる。PLINES OFFの記号変更と区別する。
- 長さの既定50 mm、表示サイズ5 mmの説明がある。6.4.7ではLENGTHが `<uval>`。
- **既定値一覧ではPLINES ON、6.4.7は既定OFFと記載。**
- 全体構文の PKEYS と個別例の PKEY は略記の関係。要素属性 PKEY と、表示スイッチの PKEYS を混同しない。
- Q REPR PLINES / Q REPR PKEYSで問い合わせ。

### 11.5 既定値一覧の記載

以下は6.3末尾の一覧の記録。別節と矛盾する値を自動採用しない。

| 設定 | 一覧の値 |
| --- | --- |
| CL | ON |
| TUBE | OFF |
| OBSTRUCTIONS | OFF |
| LEVEL | 0 |
| PPOINTS | ON、LENGTH 50、NUMBERS OFF |
| PLINES | ON、PKEYS OFF |

REPRESENTATION DEFAULTで復元する説明。

### 11.6 全体構文に含まれる追加項目

- TUBE、CL / CENTRELINE、HOLES、OBSTRUCTION、INSULATION、LEVEL、PPOINTS、PROFILE、PNODES、SNODES、POINTS、PKEYS、PLINES、MASSPROPERTIES、DARCTOLERANCE、UPDATE、DEFAULT。
- PNODES / SNODES は ON/OFF に加えて COLOUR / SIZE を指定できる。
- PPOINTSの補助構文はLENGTHの単位付き距離、NUMBERSのON/OFFを含む。
- 同じコマンドで複数の指定を反復できる。DEFAULTは別終端の経路。
- HOLES等の詳細効果や対象要素は、全体構文だけから推測しない。
- `<colno>` は整数のほか、ACTIVE、VISIBLE、CE、CLASH、OBST、COMPARE MATCHED / MISMATCHED / UNMATCHED / TEXT、AIDSを選ぶ構文。
- COMPARE UNMATCHED は CONNECTOR の追加指定経路がある。COMPARE / AIDS の詳細は未提示。
- これらの colno は用途別の色設定を参照する指定で、任意の色名と同一視しない。

## 12. 実装へ使う際の境界

- この文書にあることと、アプリが対応していることを同一視しない。
- 未対応の式・型・追加属性は原文保持を優先し、推測した実数・向きへ置き換えない。
- PARAMの意味は family・参照先・プリセットと組にする。
- 実寸評価は実部品値と設計文脈、仮配置は専用の編集メタデータとする。
- E3D向けマクロの実行可能性、表示既定値、負寸法・ゼロ寸法・単位次元の判定は、[未確認事項](open-questions.md)と実装状態を照合する。

## 13. ユーザー提示のE3D ALP FILE出力（2026-10-19）

出典：ユーザーがE3DのALP FILE出力と説明したGMSETの写真。旧PDMS資料とは別の観測情報。画像から読めた範囲であり、本ツールがE3D実機で実行して確認した結果ではない。

- INPUT BEGIN → NEW GMSET /名前 → 子要素NEWと属性代入・END → GMSETのEND → OLD/LOCK → INPUT END GMSET /名前 → INPUT FINISHの構成。
- SCYLINDER、LSNOUT、SSPHEREという長形式の型名。従来のツール内部型SCYL、LSNO、SSPHへ対応。
- CLFL/TUFLにtrue。LINEのSETPにP点列。従来の内部属性CLFLA/TUFLA/PTSへ対応。
- SUM PARAM n IPARAM m、PARAM n、係数 TIMES PARAM n、括弧内ATTRIB PARA[n]とATTRIB DESP[n]の加算式が観測できる。原文を保存し、既存の制限付き式エンジンで解釈可能なものを評価する。
- PAXIの-XとP点参照、PAAXの-X、正形状側NAPP 0がある。正形状NAPPの意味・一般的な既定値はこの観測だけで確定しないため、原文属性として保持する。
- OLD GMSET /名前、およびOLD 子型 1 OF GMSET /名前に続くLOCK。ロック対象の型・親・型別順番号を照合する。入れ子へのOLDは同じ構成を再帰的に用いるツールの実装で、写真による直接確認範囲とは区別する。
- PTSETへの同じ外枠の適用は今回のツールの共通出力方式であり、このGMSET写真による実機確認ではない。

## 14. カタログ一式とディテールテキストの追加写真（2026-10-19）

出典：GMSET写真に続けて提示されたカタログの2枚と、ユーザーが「ディテールテキストの作成データ」と説明した別の1枚。元の固有名・本文・数値配列・写真原本は保存しない。ユーザー提示の作成出力の観測情報であり、本ツールによるE3D実行検証ではない。

- 先の2枚ではINPUT BEGINの後にNEW CATEGORY、配下にSDTEXT、TEXT、SCOMPONENTがある。PURP、RTEX、STEX、GTYP、PARAが観測できる。PARAの複数行は末尾の$で継続している。
- 後半にOLD CATEGORY、OLD SDTEXT、OLD TEXT、OLD SCOMPONENTとLOCKが続く。SCOMPONENTを選択した後にPTREでPTSET、GMREでGMSETを参照し、その後LOCK、INPUT END CATEGORY /名前、INPUT FINISHで終える。参照設定がNEW本体だけでなく後段にも現れる点を保持すべきである。
- この2枚にPTSET参照はあるが、NEW PTSETとポイントの本体定義はない。PTSETの実機出力例を確認済みとは扱わない。
- ディテールテキストの写真では、INPUT BEGIN、NEW SDTEXT /名前、SKEYの引用符付き値、RTEXの引用符付き本文、END、OLD SDTEXT /同じ名前、LOCK、INPUT END SDTEXT /同じ名前、INPUT FINISHという単独要素の構成を確認できる。
- 今回ユーザーがディテールテキストと呼ぶデータはSDTEXTである。SKEYとRTEXを持つ作成形式が新たな根拠となる。別の管理用DETAILレコード全般との一対一対応、SPECの参照属性、所有先、PROPの正式型・作成形式まで確定したものではない。
- 既存のPTSET/GMSET専用読込・出力と、CATEGORY/SDTEXT等の今後の対応を区別する。写真の受領・メモ追加だけでは、カタログ一式やディテールテキストのMAC入出力を実装済みとしない。

## 15. PROPの作成データの追加写真（2026-10-19）

出典：ユーザーが「PROPの作成データです」と説明した写真。写真原本、元の固有名、数値を含むマクロ一式は公開しない。観測した構造・属性のみを記録する。

- INPUT BEGINの後にNEW CMPTYPE /親名、続けてNEW CMPDATA /子名があり、CMPDATAにCWEIの括弧付き数値を設定する。
- ENDが2回あり、CMPDATAとCMPTYPEをそれぞれ閉じた後、INPUT END CMPTYPE /親名、INPUT FINISHで終わる。
- この写真にはOLD・LOCKがない。GMSETやSDTEXTの例で観測したロック処理を、すべての出力へ必須として一般化しない。
- 今回ユーザーがPROPと呼ぶ作成データは、CMPTYPEを親、CMPDATAを子とする構造。単一のNEW PROPを作る例ではない。SMTEやSDTEXTとの同一視はしない。
- CWEIの値は確認できるが、単位、未設定時の既定値、許容式の全範囲はこの写真だけでは確定しない。kg等の単位を推測追加しない。
- SPECからCMPTYPEとCMPDATAのどちらを、どの属性で参照するか、およびCMPTYPE自身の所有先は写真にない。内部catalog_propsとの対応付けとMAC入出力は、この記録段階では未実装である。

## 16. PTSET本体の追加写真（2026-10-19）

出典：ユーザーが「こちらがptsetの作成データでした」と訂正・提示した写真。先のCATEGORY例とは別に、PTSET本体を確認できた。原写真、固有名、元のマクロ一式は公開しない。

- INPUT BEGIN、NEW PTSET /名前、NEW PTAXISによる2つの点、各END、PTSETのEND、OLD/LOCK、INPUT END PTSET /名前、INPUT FINISHの構成。
- 点属性はNUMB、PCON PARAM n、PBOR PARAM n、PDIS、PAXI。一方はPDIS 0とX、他方は括弧内でATTRIB PARA[n]・定数・ATTRIB DESP[n]を加算した距離式と-Xを持つ。
- OLD PTAXIS 順番号 OF PTSET /名前で各点を選択してLOCKする。ここでの順番号は型別メンバー順であり、接続点番号NUMBそのものとは区別する。
- PTAXISを内部PTAXIの別名として読込・出力に追加。既存のPTAXI/PTAX入力も維持する。式・PARAM参照は文字列を保持し、PCONの参照値を一律数値とはしない。
- §13時点で未観測だったPTSETのINPUT外枠とPTAXISのOLD/LOCKについて、今回写真による具体的根拠を得た。ツールのSJIS出力との往復テストは別の自作データで実施し、E3D実機での再実行確認とは区別する。

## 17. マクロ簡略化に関するユーザー情報と実装方針（2026-10-20）

ユーザーから、/名前を直接入力すれば現在要素を選択でき、OLDの付加は必須でないとの情報を得た。ALPのINPUT外枠や作成後に各要素を再選択する形式を、作成マクロ一般の必須構文としない。ユーザーは出力を簡潔にすることを明示した。

実装はINPUT/OLDなしの作成命令列と属性の同一行への集約へ変更。必要な親子のENDは保持し、任意のロックは各要素が現在要素であるEND直前に置く。子の作成途中で親を先にロックしない。LOCKはDB要素の変更を制限する命令であり、プレビューの点のドラッグ固定とは区別する。親のLOCKで子孫全体が保護される条件と配下一括ロックの正確な構文は未確認。新しい実装はその構文を推測せず、生成MACの実機再実行も未実施である。

## 18. 登録先の直接選択を出力先頭へ置く（2026-10-20）

ユーザー指定：PTSETとGMSETには決まった登録先があり、各登録先の/名前を出力冒頭に置いて現在要素を移してから作成する。OLDの付加は不要という先のユーザー情報に従う。/なしの入力は先頭へ補完する。これは既存の登録先を選択する処理であり、名前から親フォルダを新規作成する指示ではない。

実装は同一プロジェクト内で種別ごとに値を保存する。作成対象の種別に対応する登録先行をNEWより先に出力し、同じ登録先で複数セットを連続作成するときは必要のない再選択を省く。各セット末尾のENDで登録先へ戻る構成は維持する。直接選択付きマクロの読込は命令を実行せず選択名を情報として保持する。所有先の存在や型、実機での登録結果を検証したものではない。


## 17. CATE・PROP・DETAILの再提示と読込対応（2026-10-29）

ユーザーがE3D出力と明示して3種類を再提示。元の固有名・数値配列・写真は収録しない。CATEのPURP COMP、配下SDTEXTのSKEY/TTEX、TEXTのSTEX、SCOMPONENTのGTYPとPARA（数値とword混在、末尾$で複数行）、OLD後のPTRE PTSET/GMRE GMSETを確認。PROPのCMPTYPE→CMPDATA→括弧付きCWEI、DETAILの単独SDTEXT→SKEY/RTEXとOLD/LOCKを確認。マクロ末尾のINPUT ENDにはルートの型と名前がある。

この具体的な宣言形式をツールのカタログ読込へ反映し、自作の別名・別数値フィクスチャで検証した。読込は命令を実行せず、ファイル内の作成対象への後段設定を適用する。実機での再実行、SPECのDETAIL/PROP参照属性、所有先、CWEI単位・一般式の全構文の確定とは区別する。過去§14–15の「未実装」は当時の状態であり、今回の読込対応を優先する。
