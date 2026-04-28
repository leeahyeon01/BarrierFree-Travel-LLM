"""
RAG 평가 통합 실행 스크립트

사용법:
    python eval/run_eval.py --testset eval/testset_template.json [옵션]

옵션:
    --testset   테스트셋 JSON 파일 경로 (필수)
    --k         Retrieval 평가 기준 상위 k (기본 5)
    --coverage  coverage 평가 모드: keyword | gpt (기본 keyword)
    --out-json  JSON 리포트 출력 경로 (기본 eval_report.json)
    --out-md    Markdown 리포트 출력 경로 (기본 eval_report.md)
    --skip-faithfulness  Faithfulness 평가 건너뜀 (API 비용 절약)
    --skip-retrieval     Retrieval 평가 건너뜀 (relevant_ids 없을 때)
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# 상위 패키지에서 import 가능하도록 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.retrieval_eval import evaluate_retrieval_batch
from eval.faithfulness_eval import evaluate_faithfulness
from eval.coverage_eval import evaluate_coverage
from eval.rule_eval import evaluate_rules


# ── 단일 케이스 평가 ──────────────────────────────────────────────────────────

def run_case(
    case: dict,
    k: int,
    coverage_mode: str,
    skip_faithfulness: bool,
    skip_retrieval: bool,
) -> dict:
    """테스트케이스 1건 평가 후 결과 dict 반환"""
    result: dict = {
        "id":    case.get("id", ""),
        "query": case.get("query", ""),
    }
    answer        = case.get("expected_answer") or case.get("answer") or ""
    generated     = case.get("generated_answer") or answer
    context_chunks = case.get("context_chunks") or []
    requirements  = case.get("requirements") or []
    relevant_ids  = case.get("relevant_ids") or []
    retrieved_ids = case.get("retrieved_ids") or []

    # 1) Retrieval 평가
    if not skip_retrieval and (relevant_ids or retrieved_ids):
        ret = evaluate_retrieval_batch(
            [{"retrieved_ids": retrieved_ids, "relevant_ids": relevant_ids}],
            k=k,
        )
        result["retrieval"] = {
            "precision_at_k": ret["mean_precision_at_k"],
            "recall_at_k":    ret["mean_recall_at_k"],
            "mrr":            ret["mrr"],
            "k":              k,
        }
    else:
        result["retrieval"] = None

    # 2) Faithfulness 평가
    if not skip_faithfulness and generated and context_chunks:
        faith = evaluate_faithfulness(generated, context_chunks)
        result["faithfulness"] = {
            "score":       faith.score,
            "num_claims":  faith.num_claims,
            "supported":   faith.supported,
            "contradicted":faith.contradicted,
            "not_found":   faith.not_found,
            "error":       faith.error,
        }
    else:
        result["faithfulness"] = None

    # 3) Coverage 평가
    if requirements and generated:
        cov = evaluate_coverage(generated, requirements, mode=coverage_mode)
        result["coverage"] = {
            "score":            cov.score,
            "num_requirements": cov.num_requirements,
            "covered":          cov.covered,
            "missing":          cov.missing,
            "mode":             cov.mode,
            "details":          cov.details,
        }
    else:
        result["coverage"] = None

    # 4) Rule-based 평가
    rule_cfg = case.get("rule_config") or {}
    if rule_cfg and generated:
        rule = evaluate_rules(
            generated,
            expected_days=rule_cfg.get("expected_days", 1),
            sessions_per_day=rule_cfg.get("sessions_per_day", 3),
            min_hours=rule_cfg.get("min_hours", 4.0),
            max_hours=rule_cfg.get("max_hours", 10.0),
            required_groups=rule_cfg.get("required_groups"),
        )
        result["rules"] = {
            "passed": rule.passed,
            "score":  rule.score,
            "checks": [
                {"rule": c.rule, "passed": c.passed, "detail": c.detail}
                for c in rule.checks
            ],
        }
    else:
        result["rules"] = None

    return result


# ── 요약 집계 ─────────────────────────────────────────────────────────────────

def aggregate(case_results: list[dict]) -> dict:
    def avg(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    retrieval_p = [c["retrieval"]["precision_at_k"] for c in case_results if c["retrieval"]]
    retrieval_r = [c["retrieval"]["recall_at_k"]    for c in case_results if c["retrieval"]]
    retrieval_mrr = [c["retrieval"]["mrr"]          for c in case_results if c["retrieval"]]
    faith_scores  = [c["faithfulness"]["score"]      for c in case_results if c["faithfulness"]]
    cov_scores    = [c["coverage"]["score"]          for c in case_results if c["coverage"]]
    rule_scores   = [c["rules"]["score"]             for c in case_results if c["rules"]]

    return {
        "num_cases":           len(case_results),
        "retrieval": {
            "mean_precision_at_k": avg(retrieval_p),
            "mean_recall_at_k":    avg(retrieval_r),
            "mrr":                 avg(retrieval_mrr),
        },
        "faithfulness": {
            "mean_score": avg(faith_scores),
        },
        "coverage": {
            "mean_score": avg(cov_scores),
        },
        "rules": {
            "mean_score":   avg(rule_scores),
            "pass_rate":    round(sum(1 for c in case_results if c["rules"] and c["rules"]["passed"]) / max(len(rule_scores), 1), 4),
        },
    }


# ── 리포트 생성 ───────────────────────────────────────────────────────────────

def _score_emoji(score) -> str:
    if score is None:
        return "N/A"
    if score >= 0.8:
        return f"{score:.3f} ✅"
    if score >= 0.5:
        return f"{score:.3f} ⚠️"
    return f"{score:.3f} ❌"


def build_markdown(summary: dict, case_results: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ret = summary["retrieval"]
    faith = summary["faithfulness"]
    cov = summary["coverage"]
    rules = summary["rules"]

    lines = [
        f"# RAG 평가 리포트",
        f"",
        f"생성일시: {now}  |  총 케이스: {summary['num_cases']}건",
        f"",
        f"## 요약 점수",
        f"",
        f"| 지표 | 점수 |",
        f"|------|------|",
        f"| Precision@k | {_score_emoji(ret['mean_precision_at_k'])} |",
        f"| Recall@k    | {_score_emoji(ret['mean_recall_at_k'])} |",
        f"| MRR         | {_score_emoji(ret['mrr'])} |",
        f"| Faithfulness | {_score_emoji(faith['mean_score'])} |",
        f"| Coverage    | {_score_emoji(cov['mean_score'])} |",
        f"| Rules (평균) | {_score_emoji(rules['mean_score'])} |",
        f"| Rules (통과율) | {_score_emoji(rules['pass_rate'])} |",
        f"",
        f"## 케이스별 결과",
        f"",
    ]

    for case in case_results:
        lines.append(f"### [{case['id']}] {case['query']}")
        if case["retrieval"]:
            r = case["retrieval"]
            lines.append(f"- **Retrieval** P@{r['k']}={r['precision_at_k']:.3f}  R@{r['k']}={r['recall_at_k']:.3f}  MRR={r['mrr']:.3f}")
        if case["faithfulness"]:
            f_ = case["faithfulness"]
            lines.append(f"- **Faithfulness** {f_['score']:.3f}  (S={f_['supported']} C={f_['contradicted']} NF={f_['not_found']})")
        if case["coverage"]:
            c = case["coverage"]
            missing = [d["requirement"] for d in c.get("details", []) if not d.get("covered")]
            missing_str = ", ".join(missing) if missing else "없음"
            lines.append(f"- **Coverage** {c['score']:.3f}  미커버: {missing_str}")
        if case["rules"]:
            rl = case["rules"]
            checks_str = "  ".join(f"{ch['rule']}={'✅' if ch['passed'] else '❌'}" for ch in rl["checks"])
            lines.append(f"- **Rules** {checks_str}")
        lines.append("")

    return "\n".join(lines)


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RAG 평가 파이프라인 실행")
    parser.add_argument("--testset",  required=True,         help="테스트셋 JSON 경로")
    parser.add_argument("--k",        type=int, default=5,   help="Retrieval 상위 k (기본 5)")
    parser.add_argument("--coverage", default="keyword",     choices=["keyword", "gpt"])
    parser.add_argument("--out-json", default="eval_report.json")
    parser.add_argument("--out-md",   default="eval_report.md")
    parser.add_argument("--skip-faithfulness", action="store_true")
    parser.add_argument("--skip-retrieval",    action="store_true")
    args = parser.parse_args()

    testset_path = Path(args.testset)
    if not testset_path.exists():
        print(f"[오류] 테스트셋 파일을 찾을 수 없습니다: {testset_path}")
        sys.exit(1)

    with open(testset_path, encoding="utf-8") as f:
        testset = json.load(f)

    cases = testset if isinstance(testset, list) else testset.get("cases", [])
    print(f"총 {len(cases)}개 케이스 평가 시작...")

    case_results = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] {case.get('id', '')} - {case.get('query', '')[:40]}")
        result = run_case(
            case,
            k=args.k,
            coverage_mode=args.coverage,
            skip_faithfulness=args.skip_faithfulness,
            skip_retrieval=args.skip_retrieval,
        )
        case_results.append(result)

    summary = aggregate(case_results)
    report = {
        "generated_at": datetime.now().isoformat(),
        "config": {
            "k": args.k,
            "coverage_mode": args.coverage,
            "skip_faithfulness": args.skip_faithfulness,
            "skip_retrieval": args.skip_retrieval,
        },
        "summary": summary,
        "cases": case_results,
    }

    # JSON 저장
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 리포트 저장: {out_json}")

    # Markdown 저장
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(build_markdown(summary, case_results))
    print(f"Markdown 리포트 저장: {out_md}")

    # 콘솔 요약
    print("\n" + "=" * 50)
    print("  평가 요약")
    print("=" * 50)
    ret = summary["retrieval"]
    print(f"  Precision@{args.k}  : {ret['mean_precision_at_k']}")
    print(f"  Recall@{args.k}     : {ret['mean_recall_at_k']}")
    print(f"  MRR           : {ret['mrr']}")
    print(f"  Faithfulness  : {summary['faithfulness']['mean_score']}")
    print(f"  Coverage      : {summary['coverage']['mean_score']}")
    print(f"  Rules 통과율  : {summary['rules']['pass_rate']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
