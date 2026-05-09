# PDF fixtures (要追加)

AC-006 で参照する以下のファイルは **本セッションでは未作成**。実装フェーズ着手時に追加してください。

| ファイル | 内容 | 入手方法 |
|---|---|---|
| `sample.pdf` | 既知本文を持つ 3〜5 ページの PDF (再配布可ライセンス) | 本人が手元の公開可能 PDF を 1 つコピー / または LibreOffice で簡単な PDF を生成 |
| `corrupted.pdf` | ヘッダ (`%PDF-1.4\n`) のみで本体破損 | `printf '%%PDF-1.4\n' > corrupted.pdf` で作成 |

**サイズ目安**: < 100KB / 著作権の問題がない範囲で。

`tests/fixtures/pdf/` 自体は wheel に含まれない (`hatchling` のデフォルトで `src/digestkit/` のみ wheel 化、repository-structure.md §4.1)。
