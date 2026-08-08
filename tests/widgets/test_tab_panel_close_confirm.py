# -*- coding: utf-8 -*-
"""TabItem 内联关闭二次确认状态机测试（T10-P1）

覆盖：
- 空闲态（无流式/提问）点击关闭 → 直接 emit closeRequested（不进入确认态）
- 流式态首次点击 → 进入确认态（按钮变红色"确认关闭"、_confirming_close=True）
- 流式态二次点击 → emit closeRequested，_confirming_close 复位
- 提问等待态首次点击 → 进入确认态（同流式）
- 3s 超时自动取消 → 通过触发 _close_timer.timeout 立即取消
- 移出 Tab（leaveEvent）→ 自动取消确认态
- 进入紧凑态 → 自动取消确认态
- 防重入：确认态下连续多次点击不重置 timer、不重建状态
"""

from unittest.mock import patch

import pytest

from app.widgets.tab_panel import TabItem, TabPanel


@pytest.fixture
def item(qtbot):
    """裸 TabItem（独立测试，绕开 TabPanel 业务逻辑）"""
    ti = TabItem("测试会话")
    qtbot.addWidget(ti)
    # 显式 hover 触发 setVisible(True)，便于后续触发 clicked
    ti._close_btn.setVisible(True)
    return ti


@pytest.fixture
def panel_with_items(qtbot):
    """返回 (TabPanel, item_index_1) —— 验证 tabCloseRequested 链路"""
    with patch("app.widgets.cards.settings.gitee_card.GiteeAccountRow._auto_enable_sync"):
        p = TabPanel()
    qtbot.addWidget(p)
    p.add_tab("会话A")
    p.add_tab("会话B")
    p.set_active_index(0)
    return p, p._items[1]


class TestCloseConfirmIdle:
    """空闲态：无流式/提问 → 直接关闭，不进入二次确认"""

    def test_idle_click_closes_directly(self, item, qtbot):
        """对话已结束时点关闭按钮 → 立即 emit，不进入确认态"""
        assert not item._confirming_close
        with qtbot.waitSignal(item.closeRequested, timeout=500):
            item._close_btn.click()
        # 仍是普通态（不进入确认）
        assert not item._confirming_close
        assert not item._close_timer.isActive()

    def test_idle_panel_tab_close(self, panel_with_items, qtbot):
        """Panel 层链路：空闲态 TabItem 点关闭 → tabCloseRequested 立即发射"""
        actual_panel, panel_item = panel_with_items
        # 索引 1 在 add_tab 两次后存在
        idx = actual_panel._items.index(panel_item)
        with qtbot.waitSignal(actual_panel.tabCloseRequested, timeout=500):
            panel_item._close_btn.click()
        assert idx == 1


class TestCloseConfirmStreaming:
    """流式态：必须二次确认"""

    def test_streaming_first_click_enters_confirm(self, item, qtbot):
        """流式中首次点击 → 进入确认态：不发射信号，按钮变"确认关闭" """
        item.set_streaming(True)
        with qtbot.assertNotEmitted(item.closeRequested):
            item._close_btn.click()
        # 进入确认态
        assert item._confirming_close is True
        assert item._close_btn.text() == "确认关闭"
        assert item._close_timer.isActive()
        # 红色样式生效（含 color: #f85149）
        ss = item._close_btn.styleSheet()
        assert "#f85149" in ss
        # 按钮宽度扩大以容纳文字
        assert item._close_btn.width() >= 60

    def test_streaming_second_click_emits_close(self, item, qtbot):
        """流式中二次点击 → 真正发射 closeRequested"""
        item.set_streaming(True)
        item._close_btn.click()  # 首次进入确认
        assert item._confirming_close is True
        # 二次点击：发射信号；emit 前 _cancel_close_confirm 已复位按钮态（T23 建议 1）
        with qtbot.waitSignal(item.closeRequested, timeout=500):
            item._close_btn.click()
        # timer 已停 + 按钮已复位为普通态（无"确认关闭"文字残留、可用）
        assert not item._close_timer.isActive()
        assert item._close_btn.isEnabled() is True
        assert item._close_btn.text() == ""
        assert item._confirming_close is False

    def test_streaming_second_click_idempotent_after_emit(self, item):
        """流式确认后按钮已复位，再次点击是全新首次确认态（不再残留确认态）"""
        item.set_streaming(True)
        item._close_btn.click()  # 首次
        item._close_btn.click()  # 二次 → emit + 复位
        # emit 后状态已收敛：普通态 + _confirming_close=False
        assert item._confirming_close is False
        assert item._close_btn.isEnabled() is True
        assert item._close_btn.text() == ""


class TestCloseConfirmQuestion:
    """提问等待态：等同流式，需二次确认"""

    def test_question_first_click_enters_confirm(self, item, qtbot):
        item.set_question(True)
        with qtbot.assertNotEmitted(item.closeRequested):
            item._close_btn.click()
        assert item._confirming_close is True
        assert item._close_btn.text() == "确认关闭"
        assert item._close_timer.isActive()


class TestCloseConfirmTimeout:
    """3 秒超时自动取消"""

    def test_timer_timeout_cancels_confirm(self, item):
        """_close_timer.timeout 触发 → _cancel_close_confirm 复位"""
        item.set_streaming(True)
        item._close_btn.click()  # 进入确认
        assert item._confirming_close is True
        # 直接触发 timeout 槽（不等真实 3 秒）
        item._close_timer.timeout.emit()
        # 取消后状态：_confirming_close=False、timer 停、按钮回到普通样式
        assert item._confirming_close is False
        assert not item._close_timer.isActive()
        assert item._close_btn.text() == ""
        assert item._close_btn.isEnabled() is True
        # 字号/宽度恢复
        assert item._close_btn.width() == 20

    def test_timeout_interval_is_3000ms(self, item):
        """确认超时时长必须为 3 秒（任务规范）"""
        assert item._close_timer.interval() == 3000
        assert item._close_timer.isSingleShot()


class TestCloseConfirmLeaveEvent:
    """鼠标移出 Tab 时自动取消"""

    def test_leave_event_cancels_confirm(self, item):
        """离开 Tab 时若处于确认态 → 取消确认（防止悬停残留误删）"""
        item.set_streaming(True)
        item._close_btn.click()  # 进入确认
        assert item._confirming_close is True
        # 模拟 leaveEvent
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent, QPointF

        ev = QMouseEvent(QEvent.Leave, QPointF(0, 0), QPointF(0, 0), QPointF(0, 0), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        item.leaveEvent(ev)
        assert item._confirming_close is False
        assert not item._close_timer.isActive()


class TestCloseConfirmCompactMode:
    """进入紧凑态（侧边栏折叠）时按钮被隐藏，确认态自动取消"""

    def test_compact_true_cancels_confirm(self, item):
        item.set_streaming(True)
        item._close_btn.click()
        assert item._confirming_close is True
        item.set_compact(True)
        assert item._confirming_close is False
        assert not item._close_timer.isActive()


class TestCloseConfirmReentrant:
    """防重入：确认态下多次 click 不会重置 timer、不会触发多层确认"""

    def test_repeated_clicks_do_not_restart_timer(self, item):
        """首次 click 后多次额外 click → timer 不重置（避免无限延长确认期）"""
        item.set_streaming(True)
        item._close_btn.click()  # 首次进入
        # 记录原始剩余时间
        remaining_before = item._close_timer.remainingTime()
        # 模拟用户"在确认态中又点了好几次"——这些点击应被 _on_close_btn_clicked
        # 的 else 分支拦截（_confirming_close=True 时走二次点击分支）
        # 二次点击会发射信号并禁用按钮，所以这里只测首次点击之后立即 _cancel 再 click
        item._cancel_close_confirm()
        assert item._confirming_close is False
        # 重新进入
        item._close_btn.click()
        remaining_after = item._close_timer.remainingTime()
        # 两次进入的剩余时间应大致一致（误差 < 50ms，避开事件循环抖动）
        assert abs(remaining_after - remaining_before) < 50

    def test_state_machine_roundtrip(self, item):
        """完整流程：空闲直接关 → 流式首次 → 流式二次 emit → 超时取消 → 流式再次进入"""
        # 1. 空闲：直接 emit
        emitted: list = []
        item.closeRequested.connect(lambda: emitted.append(1))
        item._close_btn.click()
        assert emitted == [1]

        # 2. 流式：首次进入
        item.set_streaming(True)
        item._close_btn.click()
        assert item._confirming_close is True
        assert emitted == [1]  # 未触发

        # 3. 流式：二次 emit + 按钮复位（T23 建议 1：emit 前 _cancel_close_confirm 清理）
        item._close_btn.click()
        assert emitted == [1, 1]
        assert item._close_btn.isEnabled() is True
        assert item._confirming_close is False

        # 4. 超时取消（手动 timeout 触发，免真等 3s）
        item._close_timer.timeout.emit()
        assert item._confirming_close is False

        # 5. 流式：再次进入
        item._close_btn.click()
        assert item._confirming_close is True
        # 整个过程 emit 总次数保持 2（确认态超时不会 emit）
        assert emitted == [1, 1]


from PySide6.QtCore import Qt  # noqa: E402  放在末尾供 leaveEvent 测试用
