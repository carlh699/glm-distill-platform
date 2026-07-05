"""蒸馏引擎静态接口测试"""
import ast
import unittest
from pathlib import Path


DISTILLATION_PATH = Path(__file__).resolve().parents[1] / "app" / "engine" / "distillation.py"


def _module_tree():
    return ast.parse(DISTILLATION_PATH.read_text(encoding="utf-8"))


def _class_def(tree, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"missing class {name}")


def _function_def(tree, name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


class DistillationStaticTests(unittest.TestCase):
    def test_new_distillation_classes_are_exposed(self):
        tree = _module_tree()

        multi_teacher = _class_def(tree, "MultiTeacherDistillationTrainer")
        self.assertTrue(any(getattr(base, "id", "") == "Trainer" for base in multi_teacher.bases))
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == "compute_loss" for node in multi_teacher.body))

        progressive_config = _class_def(tree, "ProgressiveDistillationConfig")
        self.assertTrue(any(getattr(decorator, "id", "") == "dataclass" for decorator in progressive_config.decorator_list))
        self.assertTrue(
            any(
                isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "stages"
                for node in progressive_config.body
            )
        )

        callback = _class_def(tree, "DistillationCallback")
        self.assertTrue(any(getattr(base, "id", "") == "TrainerCallback" for base in callback.bases))
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == "on_step_end" for node in callback.body))


    def test_training_can_resume_from_checkpoint(self):
        tree = _module_tree()
        run_training = _function_def(tree, "run_distillation_training")
        param_names = [arg.arg for arg in run_training.args.args]

        self.assertIn("resume_from_checkpoint", param_names)

        train_calls = [
            node
            for node in ast.walk(run_training)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "train"
        ]
        self.assertTrue(
            any(
                any(keyword.arg == "resume_from_checkpoint" for keyword in call.keywords)
                for call in train_calls
            )
        )


if __name__ == "__main__":
    unittest.main()
