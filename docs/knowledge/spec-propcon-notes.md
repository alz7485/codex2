# SPEC・PROPCON 資料整理と今後の設計への適用

整理日: 2026-11-04。出典はユーザー提示の PDMS/PARAGON 資料、第12–14章、第17–20章の写真。書名・版・発行年は未確定。逐語転載ではなく技術事項の要約であり、写真・原図・私的な固有名は収録しない。

**資料の記載、ツールの設計案、実装済み機能、E3D 4.0実機確認を区別する。** 本追加は文書のみ。今回の資料から新機能を実装したものではなく、既存機能の対応範囲も変わらない。

## 1. SPEC作成・選択（12.1–12.2）

- PARAGONでSPECONMODEに入る。NEW SPECification /名前、またはNEW /名前でSPEC作成。SELEC/SPCOMは表入力から間接的に作成される。
- 既存SPECはOLD SPEC /名前、OLD /名前、SPEC /名前、直接 /名前で選択できる。FIRST/NEXT等のDB移動も利用できる。
- TEXTは引用符で囲む説明文で最大50文字。階層内のTEXTに格納され、SPEC出力時に名前の後へ表示される。
- VPRM連携情報はFISSUE（版）、FINPUTBY（由来・発行日時）、FSTATUS（作業中／承認等）。

## 2. 表形式と特殊記号（12.3）

SPECを作成／選択してから入力する。SPEC内には複数表を持てる。各表はHEADING、任意のDEFAULTS、SPCOMごとの回答行の順。

- HEADINGと次の列定義は別行。TYPEはGTYPE、NAMEはSPCOM識別名。その後に選択条件と参照列が続く。
- 新規入力とOUTPUT NEWはTYPE NAME順。通常出力・既存編集の基本形はNAME TYPE順。構文図14章には両順序があるが、用途を区別する。
- 最大20列。資料は既存SPECの列数を変更できないとする。SPCOM追加時は既存の対応する見出しと同じ構成にする。
- DEFAULTSも次行に値。TYPE/NAMEは「-」、選択列は明示値／「-」／「=」。参照列には既定値を置かない。

| 記号 | 文脈と意味 |
| --- | --- |
| * | SPECONが現在SPEC名として自動設定。所属名の省略に使う |
| + | 表の直上と同じ値（ditto） |
| - | 既定値行で未指定／該当なし。参照列の既定値には使わない |
| = | 既定値行で、他の条件が決まった後の先頭候補を採用 |
| =0 | 回答行の未設定参照。既定値の「=」と別物 |

SPREFは一意。重複相当品の名前に接尾辞を付け、ISODRAFTでは既定の区切り文字「:」以降を無視して品目コードを扱える。

選択列に単位語（FT、MM等）を文字値として置くと、直前の数値の単位と解釈され列がずれる可能性がある。STYPEは4文字までのPDMS word、または引用符付き文字列。マクロをwordから文字列へ変換する例はTEXT 'GATE'で、大文字が同等解釈の条件。禁止文字の細部は写真から確実に転記できておらず未確定。

EXTRA :UDA名 値はユーザー属性。LEXICONでSPCOMへの適用定義が必要。COMMENTは解釈対象外の注記。両者は出力・再入力で保持される。

## 3. 編集・削除・複製・出力（12.4–12.7）

- 追加行は該当部品型の表へ統合される。既存行更新ではNAME/TYPEを変更すると元行を特定できないため、値や参照の変更と識別変更を分ける。
- DELETEはDBから消去し、Design参照を事前確認しない。既存SPREFが無効になり得る。DELETE SPECはSPEC全体、DELETE ALLはSPECを残して全SPCOMを削除。
- REMOVEはCATREF/DETAIL以外の回答を除去し、SPCOMを退避SPEC「/*LIMBOSPEC」へ移す。複数Catalogue DBには別々の退避先がある。Designの検索は元SPECに見つからなければ退避先を探す。
- REMOVE ALLも可能。復帰は正しい現在SPECで、退避したSPCOM名を使って更新する。具体的な更新構文の未提示部分を推測しない。
- 複製は新しいSPECを作成後、COPY 元SPEC [RENAME 旧名部分 新名部分]。見出し・既定値・行を複製し、任意で名前部分を置換する。
- FILEで出力先を指定。既定はTERMINAL。OUTPUTはOUTPUT OLD相当、OUTPUT NEWは再入力用。複数SPECやGTYPEによる絞り込みが可能。
- COMPACTは連続空白を縮め、ALIGNEDは整列表記へ戻す。表示整形とデータの意味を分離する。
- 管径はDBでmm保存。BORES ACTUAL／NOMINAL、既定NOMINAL。呼び径出力は標準表と許容差による照合を伴い、単なる25.4倍の換算ではない。RADI/HEIGは現在の距離単位を使う。

## 4. 配管SPECの選択条件と参照（13.1）

PBORE n／PCONN nのnは点番号。PBORE0／PCONN0は幾何学的なP0ではなく、新部品の点を番号順に照合して適合する接続を探す特例。反転フランジ等に利用する。

STYPEはGTYPE内の細分類。ANGLE/RADIUSはPTSETでDDANGL/DDRADIを使う場合の要求値で、単値または範囲。TEMPERATURE/PRESSUREは運転条件、RATINGは圧力等級。SHOPはTRUE/SHOPが工場、FALSE/SITEが現地。独自の選択質問は4文字までの語と任意の数値修飾子。構造材・保温用の列も構文図にあり、配管だけの固定列としない。

| SPCOMの参照列 | 資料に記載された参照先・用途 |
| --- | --- |
| CATREF | Catalogue部品。各表に必須。先に実在しないとUndefined Nameとなり=0 |
| DETAIL | CatalogueのDTEXT。一般説明、集計表・アイソメ用 |
| MATXT | MTEXT。材料説明 |
| BLTREF | BLTAB。締結ボルト情報 |
| CMPREF | Properties DBのCMPTと13.1.4に記載（17.5.3との照合が必要） |

CATREF以外は見出しから省略、または各行で未設定にできる。SCOM（Catalogueの部品定義）とSPCOM（SPECの選択行）を混同しない。

SPEC全体のMATREF→SOLID、FLUREF→FLUIDは先頭に出力され未設定でも現れる。RATING（既定0）とLINETYPEも出力される。LINETYPEはFP＝材料コードへ長さ付加、FX＝標準コードに長さ内包、NUL＝既定の可変長。資料はこれらの設定を固定長配管のISODRAFT用途として説明する。

## 5. Properties DBの構成（17.1–17.3）

ADMINでProperties DBを作成し、使用前にMDBへ追加。PROPCONコマンドはPARAGONのコマンド行で入力する。材質物性、部品物性、CASE、拘束、解析実行情報を保持する。

| 階層 | 用途 |
| --- | --- |
| WORLD → MATW → SOLI／FLUI | 管材／流体の物性 |
| WORLD → CASWL → CASE、またはCAST → CASE | 条件と条件分類。図にはCASH表記もある |
| WORLD → CMPWL → CMPT → CMPD／TUBD | 部品／管の物性。図はCMPW表記 |
| WORLD → CONW → CONT → CONS → TCAS | 拘束種別、拘束、適用CASE |
| WORLD → RUNW → RUN → CARD | 解析実行用テキスト |
| WORLD → GPWL → GROU → CASE | CASEのグループ利用 |

SOLI/FLUIの下に物性表、その下に温度・圧力ごとの測定点を置く。密度TDEN/SDEN、許容応力TSTR/SSTR、ポアソン比TPOI/SPOI、熱膨張TEXP/SEXP、ヤング率TYOU/SYOU、汎用物性TAPR/SAPR・TBPR/SBPR・TCPR/SCPR。FLUIには許容応力・ポアソン比の表／測定点がない。

測定点はTEMP/PRESと対応する物性値（例YOUN、APRO）を持つ。補間は対応する応力解析パッケージが行う。資料上TEMPは℃、PRES/YOUNはN/m²。これを全属性の一律単位と解釈しない。

文字列上限: SOLI/FLUIのDESC120、表のPQUA4・SREF12、TAPR/TBPR/TCPRのPNAM12、同階層TEXTのSTEX50文字。

17.3.3はSPCOMのMATR/FLURがSOLI/FLUIを参照すると記述する。PIPE/BRANCHに同参照があればDesign側を優先し、未設定ならSPCOM側を使う。13.1.4のSPEC全体MATREF/FLUREFとの対応は未解決。

## 6. CASEとグループ（17.4、18）

CASEはWEFA重量係数、WPRE風圧、WIFA風係数、IPRE内圧、RPRE基準圧力、PTEM管温度、RTEM基準温度、TGRA温度勾配（実数）。SHOCは実数3要素、APPLは20文字。PIPE/BRANCHのCASRは適用CASEグループを参照する。

グループは同じCASEの重複作成を避ける仕組み。ADDで所属追加、REMOVEで所属解除。グループ内でDELETEするとCASE本体がProperties DBから消える。これはSPECの退避REMOVEと異なる文脈。GroupのFUNCは12文字。

## 7. CMPD／TUBDと計算結果（17.5）

CMPTは管理用のComponent Type、CMPDはComponent Data。20章のCMPTypes／CMPData表記は、提示マクロCMPTYPE／CMPDATAとの対応を裏付ける。

| 属性 | 意味 |
| --- | --- |
| OUTD、ACBO | 外径、実内径 |
| BTOL、WTOL | 内径公差、重量公差 |
| CWEI、CIWE | 部品重量、部品保温重量 |
| WDIA、SHAP | 風荷重用直径、形状係数 |
| RINE、SIF | 回転慣性ベクトル、応力集中係数 |
| PRFC、SDTH、CORA | 圧力係数、サドル厚さ、腐食代 |
| EFAC、BFLE | ヤング率係数、曲げ柔性 |
| DFFL、DMFL、RMFL | 変位‐力、変位‐モーメント、回転‐モーメントの柔性 |
| MRKR | 部品マーカー |

RINE/SIF/SDTHは実数3要素配列。DFFL/DMFL/RMFLは6・9成分の柔性行列だが、各属性への対応と配置順は未確認。残りの記載属性は実数。本文のPWASは一覧にないが20章にPWASTageがある。意味と適用条件は未確定。

TUBDはDFFL/DMFL/RMFLを持たず、CWEI/CIWEの代わりに単位長さ当たりのUWEI/UIWEを持つ。

CWEI/UWEIはPARAM参照式に対応し、従来の直接数値も有効。続く本文はMRKR以外の残りの実数属性もパラメータ化されたとする。配列・行列の一般式対応まで推定しない。

Designの参照元要素では、例えばQ PROPRE OUTDで計算済み物性を照会できる。17.5.3はSPCOMのCMPRが該当CMPD/TUBDを参照すると記述し、13.1.4のCMPREF→CMPTとは対象粒度が異なる。未確認事項で管理する。

## 8. 拘束・RUN（17.6–17.7）

CONSのFORC荷重、MOMEモーメント、DISP変位、ROTA回転、FLIM荷重制限、MLIMモーメント制限、DFLF並進柔性係数、RFLF回転柔性係数、FCOF摩擦係数、CPUL並進コールドプル、CPUTねじりコールドプルは実数3要素。DLIM変位制限とRLIM回転制限は6要素。APPL20文字、CONTのRTYP12文字。

TCASのCASRは適用CASEを参照し、CONSは複数TCASを持てる。TCASがない場合は任意CASEに有効という意味になり得る。DesignのPIPE配下ATTAのCSTRがProperties DBの拘束を参照する。

RUNはDATE9文字、UNAME12文字。CARDはCATYとCTXT120文字。解析パッケージ用のヘッダーや実行情報を保存する。

## 9. 数値・構文図（14、19–20）

指数は属性 値 EX 指数の形式で10のべき乗。負指数可、省略符号は正。通常表記は資料上最大11桁、EXの扱える範囲は機種依存。十分大きい／小さい値は指数形式で出力される。現代のE3D制限として11桁を直ちに実装しない。

14章はSPEC、表、見出し、既定値、回答行、ID（名前／参照番号）、COPY、単位付き値の構文を定義する。EXTRA/COMMENT/TEXT、値の範囲等を含む。一般のPDMS移動・単位・デバイス・PML等も利用できるが、全命令を読込時に実行してよいという意味ではない。

20章の<sadj>は文字列等の設定、<satt>は属性選択肢、<snoun>は要素種別、<squer>は照会対象、<watt>はPQUAlifier/MRKR。山括弧の名前は構文図の参照記号であり実行コマンドではない。略記は図で確認した個別の対応を使い、任意の型を4文字に切り詰めない。

## 10. 今後の設計で参照する方針（設計案・未実装）

1. SPECは見出し・既定値・回答行・列順を持つ表モデルとする。SCOM本体とSPCOM選択行、管理フォルダと実機所有階層を分離する。
2. 新規用と既存更新用の出力を区別し、TYPE/NAME順、名変更、見出し互換を診断する。入力原文と解決済み値を分け、特殊記号・未知属性・注記・UDAを失わない。
3. CATREFと他の参照を型付きで管理し、出力前に参照先存在・依存順・未設定を確認する。CMPREF/CMPR等の矛盾を推測で変換しない。
4. 削除、SPEC退避、グループ所属解除を別操作とする。ツール内削除を実機DELETEマクロへ自動変換しない。
5. Propertiesはスカラー／配列／行列／文字列／参照／式を区別する。CWEIを固定数値だけにせず式原文を保持し、仮値・実値・計算結果を混ぜない。
6. 呼び径と実内径、出力単位と保存単位を分離。標準呼び径表と許容差の根拠なしに数値を置換しない。
7. 物性補間、拘束解析、E3Dへの直接登録は、資料を読んだだけで対応済みとしない。対応範囲・検証結果を個別に管理する。

## 11. 未解決事項と既存記録の読み替え

- 13.1.4のCMPREF→CMPTと17.5.3のCMPR→CMPD/TUBD。親管理型と物性データのどちらが正式な参照先か、E3Dで照合する。
- SPEC全体MATREF/FLUREFとSPCOM側MATR/FLURの所属・優先順位。Design側優先の記述だけから両者を同一視しない。
- SPECのDETAIL→DTEXTとユーザー提示のSDTEXTの対応。物性CMPTYPE/CMPDATAが確認できても、この相違は解消しない。
- 13.1.5の例はDEFAULTS語なしの既定値らしい行を含む。12.3の明示構文との違いを未解決として残す。
- PWASの意味、柔性行列の成分順、物性の単位・既定値・一般式の全範囲、STYPEの禁止文字、旧11桁制限の現行性。
- CASWL/CASH、CMPWL/CMPWなどの図と本文の表記差。正式長名・略記・有効な所有先を実機で確認する。

既存の仕様メモ§15および未確認事項§14にある「PROPの型・参照が不明」は、この資料によって型名対応と資料上の参照先候補が増えたものとして読む。全項目が未解決のままとも、E3Dで全面解決済みとも扱わない。
