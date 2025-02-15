import json
from unittest import mock

import pytest

from tests.mocks.api.alerts_api_mock import MockAlertsAPI


def test_get_suppressed_alerts(alerts_api_mock: MockAlertsAPI):
    last_test_alert_sent_times = alerts_api_mock._query_last_test_alert_times()
    last_model_alert_sent_times = alerts_api_mock._query_last_model_alert_times()

    test_alerts = alerts_api_mock._query_pending_test_alerts()
    model_alerts = alerts_api_mock._query_pending_model_alerts()

    suppressed_test_alerts = alerts_api_mock._get_suppressed_alerts(
        test_alerts, last_test_alert_sent_times
    )
    suppressed_model_alerts = alerts_api_mock._get_suppressed_alerts(
        model_alerts, last_model_alert_sent_times
    )

    assert json.dumps(suppressed_test_alerts, sort_keys=True) == json.dumps(
        ["alert_id_1"], sort_keys=True
    )
    assert json.dumps(suppressed_model_alerts, sort_keys=True) == json.dumps(
        ["alert_id_1"], sort_keys=True
    )


def test_split_list_to_chunks(alerts_api_mock: MockAlertsAPI):
    mock_list = [None] * 150

    split_list = alerts_api_mock._split_list_to_chunks(mock_list, chunk_size=10)
    assert len(split_list) == 15
    for chunk in split_list:
        assert len(chunk) == 10

    split_list = alerts_api_mock._split_list_to_chunks(mock_list)
    assert len(split_list) == 3
    for chunk in split_list:
        assert len(chunk) == 50


@mock.patch("subprocess.run")
def test_update_sent_alerts(mock_subprocess_run, alerts_api_mock: MockAlertsAPI):
    mock_alerts_ids_to_update = ["mock_alert_id"] * 60
    alerts_api_mock.update_sent_alerts(
        alert_ids=mock_alerts_ids_to_update, table_name="mock_table"
    )

    # Test that alert ids were split into chunks
    assert mock_subprocess_run.call_count == 2

    calls_args = mock_subprocess_run.call_args_list
    for call_args in calls_args:
        # Test that update_sent_alerts has been called with alert_ids as arguments.
        assert call_args[0][0][1] == "run-operation"
        assert call_args[0][0][2] == "update_sent_alerts"
        assert "alert_ids" in json.loads(call_args[0][0][4])


@mock.patch("subprocess.run")
def test_skip_alerts(mock_subprocess_run, alerts_api_mock: MockAlertsAPI):
    # Create 80 alerts
    test_alerts = alerts_api_mock._query_pending_test_alerts()
    mock_alerts_ids_to_skip = test_alerts.alerts * 20

    alerts_api_mock.skip_alerts(
        alerts_to_skip=mock_alerts_ids_to_skip, table_name="mock_table"
    )

    # Test that alert ids were split into chunks
    assert mock_subprocess_run.call_count == 2

    calls_args = mock_subprocess_run.call_args_list
    for call_args in calls_args:
        # Test that update_skipped_alerts has been called with alert_ids as arguments.
        assert call_args[0][0][1] == "run-operation"
        assert call_args[0][0][2] == "update_skipped_alerts"
        assert "alert_ids" in json.loads(call_args[0][0][4])


@pytest.fixture
def alerts_api_mock() -> MockAlertsAPI:
    return MockAlertsAPI()
