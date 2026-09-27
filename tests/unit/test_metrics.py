from prometheus_client import REGISTRY

from url_shortener.entrypoints import metrics


def test_process_sampler_reports_cpu_and_memory():
    metrics.ProcessSampler().sample()

    cpu = REGISTRY.get_sample_value("app_process_cpu_seconds")
    memory = REGISTRY.get_sample_value("app_process_resident_memory_bytes")
    assert cpu is not None and cpu > 0
    assert memory is not None and memory > 0


def test_process_sampler_stops_cleanly():
    sampler = metrics.ProcessSampler(interval_seconds=0.01)

    sampler.start()
    sampler.stop()

    assert not sampler._thread.is_alive()
