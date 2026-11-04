import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.bybit_reconciliation_report import ReportError, build_report, compare_execution_snapshots

SAVED = "2026-10-01T00:00:00Z"
SAVED_MS = 1790812800000
CAPTURE_MS = SAVED_MS + 60_000


def page(rows=None):
    return {"requested_cursor": "", "response": {
        "retCode": 0, "result": {"list": rows or [], "nextPageCursor": ""}
    }}


def snapshot(position_rows=None, order_rows=None, execution_rows=None):
    raw = {
        "positions": [page(position_rows)],
        "active_orders": [page(order_rows)],
        "order_history": [{
            "interval_start_ms": SAVED_MS,
            "interval_end_ms": CAPTURE_MS,
            **page(order_rows),
        }],
        "executions": [{
            "interval_start_ms": SAVED_MS,
            "interval_end_ms": CAPTURE_MS,
            **page(execution_rows),
        }],
    }
    digest = hashlib.sha256(json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "category": "linear",
        "settle_coin": "USDT",
        "status": "CAPTURED_READ_ONLY_NOT_RECONCILED",
        "saved_at_utc": SAVED,
        "raw": raw,
        "raw_sha256": digest,
        "counts": {
            "positions": len(position_rows or []),
            "active_orders": len(order_rows or []),
            "historical_orders": len(order_rows or []),
            "executions": len(execution_rows or []),
            "position_pages": 1,
            "active_order_pages": 1,
            "order_history_pages": 1,
            "execution_pages": 1,
        },
        "order_history_coverage": {
            "status": "QUERYABLE_WINDOW_ONLY_NOT_COMPLETE",
            "start_ms": SAVED_MS,
            "end_ms": CAPTURE_MS,
            "duration_ms": CAPTURE_MS - SAVED_MS,
            "limitations": ["test fixture"],
        },
        "bybit_server_time_before_ms": CAPTURE_MS,
        "bybit_server_time_after_ms": CAPTURE_MS + 1000,
        "capture_now_ms": CAPTURE_MS,
    }


def upgrade_to_schema2(data):
    data = copy.deepcopy(data)
    data["schema_version"] = 2
    endpoint_map = {
        "positions": ("/v5/position/list", 200),
        "active_orders": ("/v5/order/realtime", 50),
        "order_history": ("/v5/order/history", 50),
        "executions": ("/v5/execution/list", 100),
    }
    for field, (endpoint, limit) in endpoint_map.items():
        groups = {}
        for page in data["raw"][field]:
            key = (page.get("interval_start_ms"), page.get("interval_end_ms"))
            groups.setdefault(key, []).append(page)
        for pages in groups.values():
            for index, page in enumerate(pages):
                params = {"category": "linear", "settleCoin": "USDT", "limit": limit}
                if "interval_start_ms" in page:
                    params.update({"startTime": page["interval_start_ms"],
                                   "endTime": page["interval_end_ms"]})
                if page["requested_cursor"]:
                    params["cursor"] = page["requested_cursor"]
                response = page["response"]
                next_cursor = response["result"].get("nextPageCursor", "")
                canonical = lambda value: json.dumps(
                    value, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False,
                ).encode("utf-8")
                page["page_provenance"] = {
                    "endpoint": endpoint, "page_index": index,
                    "request_started_at_ms": 1000 + index * 10,
                    "request_completed_at_ms": 1005 + index * 10,
                    "query_params": params,
                    "query_params_sha256": hashlib.sha256(canonical(params)).hexdigest(),
                    "requested_cursor_sha256": hashlib.sha256(page["requested_cursor"].encode()).hexdigest(),
                    "next_cursor_sha256": hashlib.sha256(next_cursor.encode()).hexdigest(),
                    "response_canonical_sha256": hashlib.sha256(canonical(response)).hexdigest(),
                    "ret_code": response["retCode"],
                    "row_count": len(response["result"]["list"]),
                    "has_next_page": bool(next_cursor),
                }
    data["raw_sha256"] = hashlib.sha256(json.dumps(
        data["raw"], ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return data


def upgrade_to_schema3(data, *, api_key="test-api-key", base_url="https://api.bybit.com"):
    data = upgrade_to_schema2(data)
    data["schema_version"] = 3
    data["api_key_fingerprint_sha256"] = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    data["base_url"] = base_url
    return data


def backup(positions=None, pending=None):
    return {
        "saved_at_utc": SAVED,
        "bot_version": "test",
        "risk": {},
        "open_positions": positions or {},
        "pending_orders": pending or {},
        "trade_seq": 0,
    }


class ReportOnlyComparatorTests(unittest.TestCase):
    def test_schema2_verifies_page_response_hash_and_query_provenance(self):
        data = upgrade_to_schema2(snapshot())
        report = build_report(backup(), data)
        self.assertEqual(report["status"], "BLOCKED_UNSUPPORTED_LOCAL_MODEL")
        tampered = copy.deepcopy(data)
        tampered["raw"]["executions"][0]["page_provenance"]["response_canonical_sha256"] = "0" * 64
        tampered["raw_sha256"] = hashlib.sha256(json.dumps(
            tampered["raw"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(ReportError, "response_canonical_sha256 mismatch"):
            build_report(backup(), tampered)

    def test_schema2_rejects_provenance_query_cursor_mismatch(self):
        data = upgrade_to_schema2(snapshot())
        data["raw"]["executions"][0]["page_provenance"]["query_params"]["cursor"] = "forged"
        data["raw_sha256"] = hashlib.sha256(json.dumps(
            data["raw"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(ReportError, "query params mismatch cursor"):
            build_report(backup(), data)

    def test_late_execution_discovered_by_refreshed_snapshot_is_not_complete(self):
        initial = upgrade_to_schema3(snapshot())
        refreshed = copy.deepcopy(initial)
        later_bound = CAPTURE_MS + 60_000
        execution = {
            "execId": "late-exec-1", "orderId": "order-late", "orderLinkId": "",
            "symbol": "BTCUSDT", "execType": "Trade", "execTime": CAPTURE_MS - 1,
            "side": "Buy", "execQty": "0.1", "execPrice": "50000", "execFee": "0.1",
        }
        refreshed["raw"]["executions"][0]["response"]["result"]["list"].append(execution)
        for field in ("executions", "order_history"):
            for page_row in refreshed["raw"][field]:
                page_row["interval_end_ms"] = later_bound
        refreshed["order_history_coverage"]["end_ms"] = later_bound
        refreshed["order_history_coverage"]["duration_ms"] = later_bound - SAVED_MS
        refreshed["bybit_server_time_before_ms"] = later_bound
        refreshed["bybit_server_time_after_ms"] = later_bound + 1000
        refreshed["capture_now_ms"] = later_bound
        refreshed["counts"]["executions"] = 1
        refreshed["raw_sha256"] = hashlib.sha256(json.dumps(
            refreshed["raw"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        refreshed = upgrade_to_schema3(refreshed)
        result = compare_execution_snapshots(initial, refreshed)
        self.assertEqual(result["status"], "LATE_EXECUTIONS_DISCOVERED")
        self.assertEqual(result["late_exec_ids"], ["late-exec-1"])
        self.assertEqual(result["subsequent_exec_ids"], [])
        self.assertFalse(result["execution_history_complete"])
        self.assertFalse(result["reconciliation_pass"])
        self.assertFalse(result["live_resume_allowed"])

    def test_execution_snapshot_comparison_rejects_changed_duplicate_identity(self):
        initial = upgrade_to_schema3(snapshot())
        refreshed = copy.deepcopy(initial)
        execution = {
            "execId": "same-id", "orderId": "order-1", "orderLinkId": "",
            "symbol": "BTCUSDT", "execType": "Trade", "execTime": CAPTURE_MS - 1,
            "side": "Buy", "execQty": "0.1", "execPrice": "50000", "execFee": "0.1",
        }
        for data in (initial, refreshed):
            data["raw"]["executions"][0]["response"]["result"]["list"] = [copy.deepcopy(execution)]
            data["counts"]["executions"] = 1
            data["raw_sha256"] = hashlib.sha256(json.dumps(
                data["raw"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")).hexdigest()
        refreshed["raw"]["executions"][0]["response"]["result"]["list"][0]["execFee"] = "0.2"
        refreshed["bybit_server_time_before_ms"] += 1000
        refreshed["bybit_server_time_after_ms"] += 1000
        refreshed["capture_now_ms"] += 1000
        for field in ("executions", "order_history"):
            for page_row in refreshed["raw"][field]:
                page_row["interval_end_ms"] += 1000
        refreshed["order_history_coverage"]["end_ms"] += 1000
        refreshed["order_history_coverage"]["duration_ms"] += 1000
        refreshed["raw_sha256"] = hashlib.sha256(json.dumps(
            refreshed["raw"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        refreshed = upgrade_to_schema3(refreshed)
        with self.assertRaisesRegex(ReportError, "execution identity changed"):
            compare_execution_snapshots(initial, refreshed)

    def test_execution_snapshot_comparison_rejects_different_api_key_fingerprint(self):
        initial = upgrade_to_schema3(snapshot())
        refreshed = upgrade_to_schema3(snapshot(), api_key="different-api-key")
        refreshed["bybit_server_time_before_ms"] += 1000
        refreshed["bybit_server_time_after_ms"] += 1000
        refreshed["capture_now_ms"] += 1000
        for field in ("executions", "order_history"):
            for page_row in refreshed["raw"][field]:
                page_row["interval_end_ms"] += 1000
        refreshed["order_history_coverage"]["end_ms"] += 1000
        refreshed["order_history_coverage"]["duration_ms"] += 1000
        refreshed = upgrade_to_schema3(refreshed, api_key="different-api-key")
        with self.assertRaisesRegex(ReportError, "same valid API-key fingerprint"):
            compare_execution_snapshots(initial, refreshed)

    def test_execution_snapshot_comparison_rejects_different_base_url(self):
        initial = upgrade_to_schema3(snapshot())
        refreshed = upgrade_to_schema3(snapshot(), base_url="https://api-testnet.bybit.com")
        refreshed["bybit_server_time_before_ms"] += 1000
        refreshed["bybit_server_time_after_ms"] += 1000
        refreshed["capture_now_ms"] += 1000
        for field in ("executions", "order_history"):
            for page_row in refreshed["raw"][field]:
                page_row["interval_end_ms"] += 1000
        refreshed["order_history_coverage"]["end_ms"] += 1000
        refreshed["order_history_coverage"]["duration_ms"] += 1000
        refreshed = upgrade_to_schema3(refreshed, base_url="https://api-testnet.bybit.com")
        with self.assertRaisesRegex(ReportError, "same Bybit base_url"):
            compare_execution_snapshots(initial, refreshed)

    def test_empty_exchange_state_still_blocks_resume_without_execution_ledger(self):
        report = build_report(backup(), snapshot())
        self.assertEqual(report["status"], "BLOCKED_UNSUPPORTED_LOCAL_MODEL")
        self.assertFalse(report["reconciliation_pass"])
        self.assertFalse(report["live_resume_allowed"])
        self.assertEqual(report["exchange"]["position_count"], 0)
        self.assertTrue(any("execution ledger" in reason for reason in report["block_reasons"]))

    def test_open_position_is_reported_but_never_quantity_reconciled(self):
        exchange_position = {
            "symbol": "BTCUSDT", "positionIdx": 0, "side": "Buy",
            "size": "0.1", "avgPrice": "50000",
            "updatedTime": CAPTURE_MS, "positionStatus": "Normal",
            "takeProfit": "70000", "stopLoss": "62000",
            "trailingStop": "0", "tpslMode": "Full",
        }
        local = backup({"BTCUSDT": {"symbol": "BTCUSDT", "direction": "long"}})
        report = build_report(local, snapshot(position_rows=[exchange_position]))
        self.assertEqual(report["exchange"]["position_count"], 1)
        self.assertEqual(report["exchange"]["positions"][0]["qty"], "0.1")
        self.assertEqual(report["exchange"]["positions"][0]["protection_status"], "EXCHANGE_STOP_CONFIGURED")
        self.assertFalse(report["reconciliation_pass"])
        self.assertIn("BTCUSDT", report["diagnostics"]["local_symbols"])

    def test_direction_conflict_is_explicit(self):
        exchange_position = {
            "symbol": "BTCUSDT", "positionIdx": 0, "side": "Sell",
            "size": "0.1", "avgPrice": "50000",
            "updatedTime": CAPTURE_MS, "positionStatus": "Normal",
        }
        local = backup({"BTCUSDT": {"symbol": "BTCUSDT", "direction": "long"}})
        report = build_report(local, snapshot(position_rows=[exchange_position]))
        self.assertEqual(report["diagnostics"]["direction_conflicts"], ["BTCUSDT"])

    def test_missing_exchange_stop_is_reported(self):
        exchange_position = {
            "symbol": "ETHUSDT", "positionIdx": 0, "side": "Buy",
            "size": "1", "avgPrice": "2500",
            "updatedTime": CAPTURE_MS, "positionStatus": "Normal",
            "takeProfit": "2600", "stopLoss": "0", "trailingStop": "0",
            "tpslMode": "Full",
        }
        report = build_report(backup(), snapshot(position_rows=[exchange_position]))
        self.assertEqual(report["exchange"]["positions"][0]["protection_status"], "NO_EXCHANGE_STOP")
        self.assertTrue(any("neither stopLoss nor trailingStop" in reason
                            for reason in report["block_reasons"]))

    def test_missing_stop_fields_are_reported_as_unknown(self):
        exchange_position = {
            "symbol": "ETHUSDT", "positionIdx": 0, "side": "Buy",
            "size": "1", "avgPrice": "2500",
            "updatedTime": CAPTURE_MS, "positionStatus": "Normal",
        }
        report = build_report(backup(), snapshot(position_rows=[exchange_position]))
        self.assertEqual(report["exchange"]["positions"][0]["protection_status"], "UNKNOWN_FIELDS_MISSING")

    def test_active_order_blocks_and_is_not_matched_to_pending_signal(self):
        order = {
            "orderId": "order-1", "orderLinkId": "", "symbol": "ETHUSDT",
            "side": "Buy", "qty": "1", "leavesQty": "1", "cumExecQty": "0",
            "orderStatus": "Untriggered", "createdTime": CAPTURE_MS,
            "updatedTime": CAPTURE_MS, "positionIdx": 0,
            "orderType": "Market", "stopOrderType": "StopLoss",
            "triggerPrice": "62000", "stopLoss": "62000",
            "takeProfit": "0", "tpslMode": "Full",
            "reduceOnly": True, "closeOnTrigger": True,
            "parentOrderLinkId": "parent-1",
        }
        local = backup(pending={"ETHUSDT": {"signal_ts": SAVED_MS}})
        report = build_report(local, snapshot(order_rows=[order]))
        self.assertEqual(report["exchange"]["active_order_ids"], ["order-1"])
        self.assertEqual(report["exchange"]["historical_order_ids"], ["order-1"])
        self.assertEqual(report["exchange"]["active_orders"][0]["position_idx"], 0)
        self.assertEqual(report["exchange"]["active_orders"][0]["parent_order_link_id"], "parent-1")
        self.assertEqual(len(report["exchange"]["conditional_orders"]), 1)
        self.assertEqual(report["exchange"]["conditional_orders"][0]["stop_order_type"], "StopLoss")
        self.assertEqual(report["local"]["pending_signal_count"], 1)
        self.assertFalse(report["live_resume_allowed"])

    def test_historical_order_status_and_coverage_are_reported(self):
        order = {
            "orderId": "history-1", "orderLinkId": "bot-order-1",
            "symbol": "BTCUSDT", "side": "Buy", "qty": "0.1",
            "leavesQty": "0", "cumExecQty": "0.1",
            "orderStatus": "Filled", "createdTime": SAVED_MS,
            "updatedTime": CAPTURE_MS, "positionIdx": 0,
        }
        report = build_report(backup(), snapshot(order_rows=[order]))
        self.assertEqual(report["exchange"]["historical_order_count"], 1)
        self.assertEqual(report["exchange"]["historical_order_statuses"]["history-1"], "Filled")
        self.assertEqual(report["exchange"]["order_history_coverage"]["status"],
                         "QUERYABLE_WINDOW_ONLY_NOT_COMPLETE")
        self.assertTrue(any("not a complete order journal" in reason
                            for reason in report["block_reasons"]))

    def test_missing_order_history_coverage_metadata_is_rejected(self):
        data = snapshot()
        data.pop("order_history_coverage")
        with self.assertRaisesRegex(ReportError, "coverage limitation metadata"):
            build_report(backup(), data)

    def test_conflicting_exec_id_across_intervals_rejects_report(self):
        execution = {
            "execId": "exec-boundary", "orderId": "order-1", "orderLinkId": "",
            "symbol": "BTCUSDT", "execType": "Trade", "execTime": CAPTURE_MS,
            "side": "Buy", "execQty": "0.1", "execPrice": "50000", "execFee": "0.1",
        }
        data = snapshot(execution_rows=[execution])
        midpoint = SAVED_MS + (CAPTURE_MS - SAVED_MS) // 2
        first = data["raw"]["executions"][0]
        first["interval_end_ms"] = midpoint
        second = copy.deepcopy(first)
        second["interval_start_ms"] = midpoint
        second["interval_end_ms"] = CAPTURE_MS
        second["response"]["result"]["list"][0]["execFee"] = "0.2"
        data["raw"]["executions"].append(second)
        first_history = data["raw"]["order_history"][0]
        first_history["interval_end_ms"] = midpoint
        second_history = copy.deepcopy(first_history)
        second_history["interval_start_ms"] = midpoint
        second_history["interval_end_ms"] = CAPTURE_MS
        data["raw"]["order_history"].append(second_history)
        data["counts"]["execution_pages"] = 2
        data["counts"]["order_history_pages"] = 2
        data["raw_sha256"] = hashlib.sha256(json.dumps(
            data["raw"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(ReportError, "conflicting duplicate execution identity"):
            build_report(backup(), data)

    def test_execution_without_local_ledger_blocks(self):
        execution = {
            "execId": "exec-1", "orderId": "order-1", "orderLinkId": "",
            "symbol": "BTCUSDT", "execType": "Trade", "execTime": CAPTURE_MS,
            "side": "Buy", "execQty": "0.1", "execPrice": "50000", "execFee": "0.1",
        }
        report = build_report(backup(), snapshot(execution_rows=[execution]))
        self.assertEqual(report["exchange"]["execution_ids"], ["exec-1"])
        self.assertTrue(any("local execution ledger" in reason for reason in report["block_reasons"]))

    def test_local_only_and_exchange_only_positions_are_both_reported(self):
        exchange_position = {
            "symbol": "ETHUSDT", "positionIdx": 0, "side": "Buy",
            "size": "0.5", "avgPrice": "2500",
            "updatedTime": CAPTURE_MS, "positionStatus": "Normal",
            "takeProfit": "0", "stopLoss": "2400",
            "trailingStop": "0",
        }
        local = backup({
            "BTCUSDT": {"symbol": "BTCUSDT", "direction": "long"},
        })
        report = build_report(local, snapshot(position_rows=[exchange_position]))

        self.assertEqual(report["diagnostics"]["local_symbols_missing_on_exchange"], ["BTCUSDT"])
        self.assertEqual(report["diagnostics"]["exchange_symbols_missing_locally"], ["ETHUSDT"])
        self.assertFalse(report["reconciliation_pass"])
        self.assertFalse(report["live_resume_allowed"])
        self.assertTrue(any("exact position reconciliation is unsupported" in reason
                            for reason in report["block_reasons"]))

    def test_non_object_snapshot_is_rejected(self):
        with self.assertRaisesRegex(ReportError, "snapshot root must be an object"):
            build_report(backup(), [])

    def test_wrong_market_scope_is_rejected(self):
        data = snapshot()
        data["settle_coin"] = "USDC"
        with self.assertRaisesRegex(ReportError, "not scoped to Bybit linear/USDT"):
            build_report(backup(), data)

    def test_raw_hash_tampering_is_rejected(self):
        data = snapshot()
        data["raw"]["positions"][0]["response"]["result"]["list"].append({"x": 1})
        with self.assertRaisesRegex(ReportError, "raw_sha256 mismatch"):
            build_report(backup(), data)

    def test_backup_timestamp_mismatch_is_rejected(self):
        data = snapshot()
        data["saved_at_utc"] = "2026-10-01T00:01:00Z"
        with self.assertRaisesRegex(ReportError, "does not match local backup"):
            build_report(backup(), data)

    def test_boolean_count_is_rejected(self):
        data = snapshot()
        data["counts"]["positions"] = False
        with self.assertRaisesRegex(ReportError, "counts.positions"):
            build_report(backup(), data)

    def test_execution_interval_gap_is_rejected(self):
        data = snapshot()
        data["raw"]["executions"][0]["interval_start_ms"] += 1
        data["raw"]["order_history"][0]["interval_start_ms"] += 1
        data["raw_sha256"] = hashlib.sha256(json.dumps(
            data["raw"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(ReportError, "not contiguous"):
            build_report(backup(), data)

    def test_future_exchange_time_is_rejected_if_not_after_backup(self):
        data = snapshot()
        data["bybit_server_time_before_ms"] = SAVED_MS - 1
        data["bybit_server_time_after_ms"] = SAVED_MS
        data["capture_now_ms"] = SAVED_MS - 1
        with self.assertRaisesRegex(ReportError, "server-time bounds"):
            build_report(backup(), data)


if __name__ == "__main__":
    unittest.main()
