document.addEventListener('DOMContentLoaded', function () {
    // 初始化用户名
    const username = localStorage.getItem('username') || '点击输入姓名';
    document.getElementById('username').textContent = username;

    // 用户名编辑
    document.getElementById('username').addEventListener('blur', function () {
        const newUsername = this.textContent.trim();
        if (newUsername && newUsername !== '点击输入姓名') {
            localStorage.setItem('username', newUsername);
            updateStreak();
            fetchAndRenderCalendar();
        }
    });

    document.getElementById('username').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            this.blur();
        }
    });

    // 初始化日历
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'zh-cn',
        firstDay: 1,  // Start with Monday
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: ''  
        },
        dayCellDidMount: function(arg) {
            // Add light red background for weekends
            if (arg.date.getDay() === 0 || arg.date.getDay() === 6) {
                arg.el.style.backgroundColor = '#ffebee';
            }
        },
        eventContent: function(arg) {
            return {
                html: `<div style="text-align: center; width: 100%;">${arg.event.title}</div>`
            };
        }
    });
    calendar.render();

    // 更新当前时间
    function updateCurrentTime() {
        const now = new Date();
        document.getElementById('current-time').textContent =
            `当前时间：${now.toLocaleTimeString('zh-cn')}`;
    }
    setInterval(updateCurrentTime, 1000);
    updateCurrentTime();

    document.getElementById('checkin-btn').addEventListener('click', async function() {
        const username = document.getElementById('username').textContent;
        if (!username || username === '点击输入姓名') {
            showNotification('请先输入用户名！');
            return;
        }
        
        await handleCheckin(username);
    });

    // 添加通知函数
    function showNotification(message, duration = 3000) {
        const notification = document.getElementById('notification');
        notification.textContent = message;
        notification.style.display = 'block';

        setTimeout(() => {
            notification.style.display = 'none';
        }, duration);
    }

    // 添加所有用户连续打卡展示函数
    async function updateAllStreaks() {
        try {
            const response = await fetch('/get_all_streaks');
            const streaks = await response.json();

            const streaksHtml = streaks.map(streak => {
                let statusClass, streakText;
                if (streak.streak === 0) {
                    statusClass = 'inactive';
                    streakText = '尚未打卡';
                } else {
                    statusClass = streak.streak > 0 ? 'early' : 'late';
                    streakText = streak.streak > 0 ? 
                        `早睡第 ${streak.streak} 天` : 
                        `晚睡第 ${Math.abs(streak.streak)} 天`;
                }
                return `
                    <div class="streak-item ${statusClass}">
                        ${streak.username} ${streakText}
                    </div>
                `;
            }).join('');

            document.getElementById('all-streaks').innerHTML = streaksHtml;
        } catch (error) {
            console.error('获取连续打卡统计失败:', error);
        }
    }

    // 获取并更新连续打卡天数
    async function updateStreak() {
        const username = localStorage.getItem('username');
        if (!username) return;

        try {
            const response = await fetch(`/get_streak/${username}`);
            const data = await response.json();
            const streakEl = document.getElementById('streak-info');
            
            if (data.streak === 0) {
                streakEl.textContent = '尚未打卡';
                streakEl.className = 'no-streak';
            } else {
                const streakText = data.streak > 0 ? 
                    `早睡第 ${data.streak} 天` : 
                    `晚睡第 ${Math.abs(data.streak)} 天`;
                streakEl.textContent = streakText;
                streakEl.className = data.streak > 0 ? 'early' : 'late';
            }
        } catch (error) {
            console.error('获取连续打卡天数失败:', error);
        }
    }

    // 获取并渲染日历数据
    async function fetchAndRenderCalendar() {
        try {
            const response = await fetch('/get_checkins');
            const checkins = await response.json();

            // 清除现有事件
            calendar.removeAllEvents();

            // 添加新事件
            const events = checkins.map(checkin => ({
                title: `${checkin.username} ${checkin.check_time}`,
                date: checkin.check_date,
                backgroundColor: checkin.is_early ? '#4CAF50' : '#f44336'
            }));

            calendar.addEventSource(events);
        } catch (error) {
            console.error('获取打卡记录失败:', error);
        }
    }

    // 添加打卡处理函数
    async function handleCheckin(username, isConfirmed = false) {
        try {
            const response = await fetch('/checkin', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username,
                    confirmed: isConfirmed
                })
            });

            const data = await response.json();

            if (response.ok) {
                if (data.needsConfirmation && !isConfirmed) {
                    // 显示确认弹窗
                    const modal = document.getElementById('confirm-modal');
                    const message = document.getElementById('confirm-message');
                    message.textContent = `您今天已经在 ${data.previousTime} 打过卡了，确定要更新打卡时间吗？`;
                    modal.classList.add('show');

                    // 处理确认按钮
                    document.getElementById('confirm-yes').onclick = async () => {
                        modal.classList.remove('show');
                        await handleCheckin(username, true);
                    };

                    // 处理取消按钮
                    document.getElementById('confirm-no').onclick = () => {
                        modal.classList.remove('show');
                    };

                    return;
                }

                showNotification(data.message);
                await updateStreak();
                await fetchAndRenderCalendar();
                await fetchAndRenderRecords();
                await updateAllStreaks();
            }
        } catch (error) {
            console.error('打卡失败:', error);
            showNotification('打卡失败，请重试！');
        }
    }

    // 获取并渲染打卡记录
    async function fetchAndRenderRecords() {
        try {
            const response = await fetch('/get_checkins');
            const checkins = await response.json();

            const recordsHtml = checkins.map(checkin => `
                <div class="record-item ${checkin.is_early ? 'early' : 'late'}">
                    ${checkin.username} 在 ${checkin.check_date} ${checkin.check_time} 
                    ${checkin.is_early ? '早睡打卡' : '晚睡打卡'}
                </div>
            `).join('');

            document.getElementById('checkin-records').innerHTML = recordsHtml;
        } catch (error) {
            console.error('获取打卡记录失败:', error);
        }
    }

    // 初始化页面数据
    updateStreak();
    fetchAndRenderCalendar();
    fetchAndRenderRecords();
    updateAllStreaks();
});