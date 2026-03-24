"""脚質判定ユーティリティ

通過順位と出走頭数から脚質区分を判定する。
JV-DataのKyakusituKubunの近似（一致率約94%）。

判定基準:
  1=逃げ: いずれかのコーナーで1番手
  2=先行: 4角比率 ≤ 31%
  3=差し: 4角比率 ≤ 67%
  4=追込: 4角比率 > 67%

注意: JRA公式の判定ロジックは非公開。本関数は通過順位からの近似であり、
ラップタイムやレース展開等を考慮していないため約6%の不一致がある。
"""


def classify_kyakusitu(jyuni4c: int, syussotosu: int,
                       jyuni1c: int = None, jyuni2c: int = None,
                       jyuni3c: int = None) -> int:
    """通過順位と出走頭数から脚質区分を判定する。

    Args:
        jyuni4c: 4角通過順位 (1〜)
        syussotosu: 出走頭数
        jyuni1c: 1角通過順位 (任意)
        jyuni2c: 2角通過順位 (任意)
        jyuni3c: 3角通過順位 (任意)

    Returns:
        脚質区分 (1=逃げ, 2=先行, 3=差し, 4=追込, 0=判定不能)

    Examples:
        >>> classify_kyakusitu(1, 16, jyuni1c=1)
        1
        >>> classify_kyakusitu(3, 16, jyuni1c=3)
        2
        >>> classify_kyakusitu(8, 16)
        3
        >>> classify_kyakusitu(14, 16)
        4
    """
    if not jyuni4c or not syussotosu or syussotosu <= 0 or jyuni4c <= 0:
        return 0

    # いずれかのコーナーで1番手 → 逃げ
    corners = [c for c in [jyuni1c, jyuni2c, jyuni3c, jyuni4c] if c and c > 0]
    if corners and min(corners) == 1:
        return 1

    # 4角の相対位置で判定
    ratio = jyuni4c / syussotosu * 100

    if ratio <= 31:
        return 2  # 先行
    elif ratio <= 67:
        return 3  # 差し
    else:
        return 4  # 追込


KYAKUSITU_NAMES = {
    0: "不明",
    1: "逃げ",
    2: "先行",
    3: "差し",
    4: "追込",
}


def kyakusitu_name(kubun: int) -> str:
    """脚質区分コードから名称を返す。

    Args:
        kubun: 脚質区分 (0-4)

    Returns:
        脚質名称

    Examples:
        >>> kyakusitu_name(1)
        '逃げ'
    """
    return KYAKUSITU_NAMES.get(kubun, "不明")
