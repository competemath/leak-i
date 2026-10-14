"""embed_loader.load: the cache first, then the Hub with a patient back-off; never a crash because the Hub had a bad minute."""

import unittest

import embed_loader


class Fake:
    """A SentenceTransformer stand-in: `cached` says whether the local cache holds the model; `hub_failures` how many network tries fail first."""

    def __init__(self, cached: bool, hub_failures: int = 0):
        self.cached, self.hub_failures, self.calls = cached, hub_failures, []

    def __call__(self, name, local_files_only=False):
        self.calls.append(("local" if local_files_only else "hub", name))
        if local_files_only:
            if not self.cached:
                raise OSError("not in the cache")
            return f"model:{name}"
        if self.hub_failures > 0:
            self.hub_failures -= 1
            raise OSError("429 Too Many Requests" if self.hub_failures % 2 else "500 Internal Server Error")
        return f"model:{name}"


class Load(unittest.TestCase):
    def test_a_baked_in_model_is_loaded_from_the_cache_and_the_hub_is_never_asked(self):
        f = Fake(cached=True, hub_failures=99)
        self.assertEqual(embed_loader.load(f, "m", sleep=lambda s: self.fail("slept")), "model:m")
        self.assertEqual(f.calls, [("local", "m")])

    def test_an_empty_cache_goes_to_the_hub_and_survives_a_bad_few_minutes(self):
        f, slept = Fake(cached=False, hub_failures=4), []
        self.assertEqual(embed_loader.load(f, "m", sleep=slept.append), "model:m")
        self.assertEqual([c[0] for c in f.calls], ["local", "hub", "hub", "hub", "hub", "hub"])
        self.assertEqual(slept, [5.0, 10.0, 20.0, 40.0])

    def test_the_wait_doubles_but_never_passes_the_cap(self):
        f, slept = Fake(cached=False, hub_failures=6), []
        embed_loader.load(f, "m", attempts=8, first_delay=50, max_delay=120, sleep=slept.append)
        self.assertEqual(slept, [50, 100, 120, 120, 120, 120])

    def test_a_hub_that_never_answers_ends_in_a_clear_error_after_the_attempts_and_no_sleep_after_the_last(self):
        f, slept = Fake(cached=False, hub_failures=99), []
        with self.assertRaises(RuntimeError) as cm:
            embed_loader.load(f, "m", attempts=3, sleep=slept.append)
        self.assertIn("after 3 attempts", str(cm.exception))
        self.assertIsInstance(cm.exception.__cause__, OSError)
        self.assertEqual(len(slept), 2)
        self.assertEqual(sum(1 for c in f.calls if c[0] == "hub"), 3)


if __name__ == "__main__":
    unittest.main()
