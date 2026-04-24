import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "btc_adaptive_hyperliquid.py"
CONFIG = ROOT / "config" / "default.json"

spec = importlib.util.spec_from_file_location("engine", SCRIPT)
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class DecisionEngineTests(unittest.TestCase):
    def test_config_safety_bounds(self):
        cfg = engine.deep_merge(engine.DEFAULT_CONFIG, json.loads(CONFIG.read_text()))
        self.assertTrue(cfg["dry_run_default"])
        self.assertLessEqual(cfg["risk"]["per_trade_ratio_max"], 0.80)
        self.assertGreater(cfg["risk"]["emergency_loss_pct"], cfg["risk"]["soft_loss_pct"])

    def test_demo_outputs_plan(self):
        cfg = engine.deep_merge(engine.DEFAULT_CONFIG, json.loads(CONFIG.read_text()))
        market = engine.normalize_market({
            "symbol": "BTC",
            "price": 78550,
            "funding_rate": 0.00012,
            "candles_1h": engine.synthetic_candles(),
            "source": "synthetic-demo"
        })
        account = engine.normalize_account({"equity": 1000, "available": 950})
        position = engine.normalize_position({"side": "flat", "size": 0})
        plan = engine.action_plan(cfg, account, position, market, {}, "normal")
        self.assertIn(plan["action"], {"noop", "hold", "open_long", "open_short", "reduce", "close_all", "scale_in", "halt_new_entries"})
        self.assertTrue(plan["dry_run"])
        self.assertFalse(plan["risk_controls"]["script_submits_orders"])

    def test_mixed_position_closes(self):
        cfg = engine.deep_merge(engine.DEFAULT_CONFIG, json.loads(CONFIG.read_text()))
        market = engine.normalize_market(json.loads((ROOT / "examples" / "market.sample.json").read_text()))
        account = engine.normalize_account({"equity": 1000, "available": 900})
        position = engine.normalize_position({"positions": [{"side": "long", "size": 1, "entry_price": 75000}, {"side": "short", "size": 1, "entry_price": 76000}]})
        plan = engine.action_plan(cfg, account, position, market, {}, "normal")
        self.assertEqual(plan["action"], "close_all")
        self.assertEqual(plan["reason_code"], "mixed_hedge_position_detected")
        self.assertTrue(plan["risk_controls"]["reduce_only_required"])


if __name__ == "__main__":
    unittest.main()
