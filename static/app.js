// Crisis Survival - Web MVP Frontend Logic

class CrisisSurvivalGame {
    constructor() {
        this.ws = null;
        this.playerId = null;
        this.playerName = '';
        this.matchTimer = null;
        this.matchTimeLeft = 60;
        this.isSoloMode = false;
        this.connectTimeout = null;
        this.intentionalClose = false;

        this.initElements();
        this.bindEvents();
    }

    initElements() {
        // Screens
        this.screens = {
            home: document.getElementById('home-screen'),
            matching: document.getElementById('matching-screen'),
            game: document.getElementById('game-screen')
        };

        // Home
        this.playerNameInput = document.getElementById('player-name');
        this.soloBtn = document.getElementById('solo-btn');
        this.multiBtn = document.getElementById('multi-btn');

        // Matching
        this.queueSize = document.getElementById('queue-size');
        this.matchTimerEl = document.getElementById('match-timer');
        this.cancelMatchBtn = document.getElementById('cancel-match-btn');

        // Game
        this.currentRoundEl = document.getElementById('current-round');
        this.maxRoundsEl = document.getElementById('max-rounds');
        this.phaseNameEl = document.getElementById('phase-name');
        this.playersBar = document.getElementById('players-bar');
        this.messageLog = document.getElementById('message-log');

        // Phase contents
        this.phases = {
            crisis: document.getElementById('crisis-phase'),
            crisisReveal: document.getElementById('crisis-reveal'),
            scavenge: document.getElementById('scavenge-phase'),
            judgment: document.getElementById('judgment-phase'),
            roundEnd: document.getElementById('round-end'),
            gameOver: document.getElementById('game-over')
        };

        this.keywordOptions = document.getElementById('keyword-options');
        this.crisisName = document.getElementById('crisis-name');
        this.crisisScenario = document.getElementById('crisis-scenario');
        this.itemsGrid = document.getElementById('items-grid');
        this.judgmentResults = document.getElementById('judgment-results');
        this.roundScores = document.getElementById('round-scores');
        this.finalRankings = document.getElementById('final-rankings');

        // Narrator and Comments
        this.narratorText = document.getElementById('narrator-text');

        // Small UX helpers (make connection failures visible without DevTools)
        this.homeHintEl = document.querySelector('#home-screen .hint');
        this.homeHintDefault = this.homeHintEl ? this.homeHintEl.textContent : '';

        this.matchingTitleEl = document.querySelector('#matching-screen h2');
        this.matchingQueueRowEl = this.queueSize ? this.queueSize.closest('p') : null;
        this.matchingTimerRowEl = this.matchTimerEl ? this.matchTimerEl.closest('p') : null;
        this.cancelMatchBtnDefault = this.cancelMatchBtn ? this.cancelMatchBtn.textContent : '';
    }

    setNarrator(text) {
        this.narratorText.textContent = text;
    }

    setHomeHint(text) {
        if (this.homeHintEl) {
            this.homeHintEl.textContent = text;
        }
    }

    resetHomeHint() {
        if (this.homeHintEl) {
            this.homeHintEl.textContent = this.homeHintDefault;
        }
    }

    prepareMatchingScreen() {
        if (this.isSoloMode) {
            if (this.matchingTitleEl) this.matchingTitleEl.textContent = '单人模式准备中...';
            if (this.matchingQueueRowEl) this.matchingQueueRowEl.style.display = 'none';
            if (this.matchingTimerRowEl) this.matchingTimerRowEl.style.display = 'none';
            if (this.cancelMatchBtn) this.cancelMatchBtn.textContent = '返回';
            return;
        }

        if (this.matchingTitleEl) this.matchingTitleEl.textContent = '匹配中...';
        if (this.matchingQueueRowEl) this.matchingQueueRowEl.style.display = '';
        if (this.matchingTimerRowEl) this.matchingTimerRowEl.style.display = '';
        if (this.cancelMatchBtn) this.cancelMatchBtn.textContent = this.cancelMatchBtnDefault || '取消匹配';
    }

    bindEvents() {
        this.soloBtn.addEventListener('click', () => this.startSoloGame());
        this.multiBtn.addEventListener('click', () => this.startMatching());
        this.cancelMatchBtn.addEventListener('click', () => this.cancelMatching());
        document.getElementById('play-again-btn').addEventListener('click', () => this.playAgain());
        document.getElementById('exit-btn').addEventListener('click', () => this.exitGame());

        this.playerNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.startSoloGame();
        });
    }

    exitGame() {
        if (confirm('确定要退出吗？AI 将接管你的角色继续游戏。')) {
            this.send({ type: 'exit_game' });
            if (this.ws) {
                this.intentionalClose = true;
                this.ws.close();
            }
            this.showScreen('home');
            this.log('已退出游戏');
        }
    }

    showScreen(screenName) {
        Object.values(this.screens).forEach(s => s.classList.remove('active'));
        this.screens[screenName].classList.add('active');
    }

    showPhase(phaseName) {
        Object.values(this.phases).forEach(p => p.classList.remove('active'));
        if (this.phases[phaseName]) {
            this.phases[phaseName].classList.add('active');
        }
    }

    log(message) {
        const msg = document.createElement('div');
        msg.className = 'log-message';
        msg.textContent = message;
        this.messageLog.appendChild(msg);

        setTimeout(() => msg.remove(), 3000);
    }

    // ========================================
    // WebSocket Connection
    // ========================================

    connect() {
        // If user opens static/index.html directly (file://), host will be empty and WS can't work.
        if (!window.location.host) {
            const msg = '请先启动后端，并通过 http://127.0.0.1:8000/ 打开页面（不要直接双击 static/index.html）。';
            this.setHomeHint(msg);
            alert(msg);
            return;
        }

        // Close any previous connection first.
        if (this.ws) {
            try {
                this.intentionalClose = true;
                this.ws.close();
            } catch (_) { }
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${encodeURIComponent(this.playerName)}`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('Connected to server');
            clearTimeout(this.connectTimeout);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.ws.onclose = () => {
            console.log('Disconnected');
            clearTimeout(this.connectTimeout);
            if (this.intentionalClose) {
                this.intentionalClose = false;
                return;
            }

            const msg = '连接断开：请确认后端已启动（python server.py），并刷新页面重试。';
            this.setHomeHint(msg);
            alert(msg);
            this.showScreen('home');
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            clearTimeout(this.connectTimeout);
            if (this.intentionalClose) {
                this.intentionalClose = false;
                return;
            }

            const msg = '连接错误：请确认后端已启动（python server.py），并刷新页面重试。';
            this.setHomeHint(msg);
            alert(msg);
            this.showScreen('home');
        };

        // Give a visible failure if the handshake never completes.
        clearTimeout(this.connectTimeout);
        this.connectTimeout = setTimeout(() => {
            if (!this.ws || this.ws.readyState === WebSocket.OPEN) return;

            const msg = '连接超时：请确认后端正在运行（python server.py）且端口为 8000。';
            this.setHomeHint(msg);
            alert(msg);
            this.intentionalClose = true;
            try { this.ws.close(); } catch (_) { }
            this.showScreen('home');
        }, 5000);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    handleMessage(data) {
        console.log('Received:', data);

        switch (data.type) {
            case 'connected':
                this.playerId = data.player_id;
                if (this.isSoloMode) {
                    this.send({ type: 'start_solo' });
                } else {
                    this.send({ type: 'start_matching' });
                }
                break;

            case 'matching_started':
                this.queueSize.textContent = data.queue_size;
                break;

            case 'matching_cancelled':
                this.showScreen('home');
                clearInterval(this.matchTimer);
                break;

            case 'game_starting':
                this.onGameStart(data);
                break;

            case 'round_start':
                this.onRoundStart(data);
                break;

            case 'phase_change':
                this.onPhaseChange(data);
                break;

            case 'keyword_options':
                this.showKeywordOptions(data.options);
                break;

            case 'keyword_submitted':
                this.log(`${data.player} 已选择关键词`);
                this.setNarrator(`等待其他玩家选择中...`);
                break;

            case 'generating_crisis':
                this.phaseNameEl.textContent = '正在融合危机...';
                this.setNarrator('🧠 AI 正在将你们的选择融合成绝望的危机...');
                break;

            case 'crisis_revealed':
                this.showCrisisReveal(data);
                break;

            case 'item_grabbed':
                this.onItemGrabbed(data);
                break;

            case 'grab_failed':
                this.log(data.message);
                break;

            case 'judging':
                this.phaseNameEl.textContent = '命运审判中...';
                this.setNarrator('⚖️ AI 正在判定你们的生死...');
                break;

            case 'judgment_result':
                this.showJudgmentResult(data);
                break;

            case 'round_end':
                this.showRoundEnd(data);
                break;

            case 'game_over':
                this.showGameOver(data);
                break;
        }
    }

    // ========================================
    // Matching
    // ========================================

    startSoloGame() {
        this.playerName = this.playerNameInput.value.trim() || '匿名玩家';
        this.isSoloMode = true;
        this.resetHomeHint();
        this.showScreen('matching');
        this.prepareMatchingScreen();
        this.connect();
        // 连接成功后会自动发送 start_solo
    }

    startMatching() {
        this.playerName = this.playerNameInput.value.trim() || '匿名玩家';
        this.isSoloMode = false;
        this.showScreen('matching');
        this.prepareMatchingScreen();
        this.matchTimeLeft = 30;
        this.matchTimerEl.textContent = this.matchTimeLeft;

        this.matchTimer = setInterval(() => {
            this.matchTimeLeft--;
            this.matchTimerEl.textContent = this.matchTimeLeft;

            if (this.matchTimeLeft <= 0) {
                clearInterval(this.matchTimer);
            }
        }, 1000);

        this.connect();
    }

    cancelMatching() {
        clearInterval(this.matchTimer);
        if (!this.isSoloMode) {
            this.send({ type: 'cancel_matching' });
        }
        if (this.ws) {
            this.intentionalClose = true;
            this.ws.close();
        }
        this.showScreen('home');
    }

    // ========================================
    // Game Events
    // ========================================

    onGameStart(data) {
        clearInterval(this.matchTimer);
        this.showScreen('game');

        this.playersBar.innerHTML = '';
        data.players.forEach(p => {
            const chip = document.createElement('div');
            chip.className = 'player-chip' + (p.is_bot ? ' is-bot' : '');
            chip.innerHTML = `<span class="name">${p.name}</span><span class="score">0分</span>`;
            chip.dataset.name = p.name;
            this.playersBar.appendChild(chip);
        });

        this.log('游戏开始！');
    }

    onRoundStart(data) {
        this.currentRoundEl.textContent = data.round;
        this.maxRoundsEl.textContent = data.max_rounds;
        this.phaseNameEl.textContent = `第 ${data.round} 轮`;
        this.judgmentResults.innerHTML = '';
        this.keywordOptions.innerHTML = '';  // 清除上一轮的选项
        this.itemsGrid.innerHTML = '';  // 清除上一轮的物品
        this.setNarrator(`第 ${data.round} 轮开始！准备好了吗？`);
        this.log(`第 ${data.round} 轮开始`);
    }

    onPhaseChange(data) {
        switch (data.phase) {
            case 'crisis_setup':
                this.phaseNameEl.textContent = '危机设定阶段';
                this.setNarrator('请选择一个关键词贡献给危机...');
                this.showPhase('crisis');
                break;

            case 'scavenge':
                this.phaseNameEl.textContent = '抢夺物资阶段';
                this.setNarrator('🎯 快点击抢夺物品！手慢无！');
                this.showScavengePhase(data.items);
                break;

            case 'judgment':
                this.phaseNameEl.textContent = '命运审判阶段';
                this.setNarrator('命运即将揭晓...');
                this.showPhase('judgment');
                break;
        }
    }

    // ========================================
    // Crisis Phase
    // ========================================

    showKeywordOptions(options) {
        this.keywordOptions.innerHTML = '';
        options.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'option-btn';
            btn.textContent = opt;
            btn.addEventListener('click', () => this.selectKeyword(opt, btn));
            this.keywordOptions.appendChild(btn);
        });
    }

    selectKeyword(keyword, btn) {
        document.querySelectorAll('.option-btn').forEach(b => {
            b.classList.remove('selected');
            b.disabled = true;
        });
        btn.classList.add('selected');

        this.send({ type: 'keyword_choice', choice: keyword });
        this.setNarrator(`✅ 已选择「${keyword}」，等待其他玩家...`);
        this.log(`你选择了: ${keyword}`);
    }

    showCrisisReveal(data) {
        this.showPhase('crisisReveal');
        this.crisisName.textContent = `☠️ ${data.name}`;
        this.crisisScenario.textContent = data.scenario;
        this.setNarrator(`危机降临！请准备抢夺物资...`);
        this.log(`危机: ${data.name}`);
    }

    // ========================================
    // Scavenge Phase
    // ========================================

    showScavengePhase(items) {
        this.showPhase('scavenge');
        this.itemsGrid.innerHTML = '';

        const tierIcons = {
            legendary: '⭐',
            normal: '📦',
            trash: '🗑️'
        };

        items.forEach((item, index) => {
            const card = document.createElement('div');
            card.className = `item-card ${item.tier}`;
            card.dataset.index = index;
            card.innerHTML = `
                <div class="tier-icon">${tierIcons[item.tier] || '?'}</div>
                <div class="item-name">${item.name}</div>
            `;
            card.addEventListener('click', () => this.grabItem(index, card));
            this.itemsGrid.appendChild(card);
        });
    }

    grabItem(index, card) {
        if (card.classList.contains('grabbed')) return;

        this.setNarrator('✅ 已抢到物品，等待其他玩家...');
        this.send({ type: 'grab_item', index: index });
    }

    onItemGrabbed(data) {
        const card = this.itemsGrid.querySelector(`[data-index="${data.item_index}"]`);
        if (card) {
            card.classList.add('grabbed');
            card.innerHTML += `<div class="grabbed-by">${data.player}</div>`;
        }

        this.log(`${data.player} 抢到了 ${data.item_name}！`);

        // 只显示自己的大师点评
        if (data.player === this.playerName) {
            this.clearComments();  // 清除之前的
            this.addComment(data.player, data.item_name, data.comment);
        }

        // 更新玩家显示
        const chip = this.playersBar.querySelector(`[data-name="${data.player}"]`);
        if (chip) {
            chip.innerHTML = `<span class="name">${data.player}</span><span class="item">📦</span>`;
        }
    }

    // ========================================
    // Judgment Phase
    // ========================================

    showJudgmentResult(data) {
        const card = document.createElement('div');
        card.className = `judgment-card ${data.survived ? 'survived' : 'died'}`;
        card.innerHTML = `
            <div class="player-name">
                <span class="result-icon">${data.survived ? '✅' : '💀'}</span>
                ${data.player}
            </div>
            <div class="item-used">物品: ${data.item}</div>
            <div class="story">${data.story}</div>
        `;
        this.judgmentResults.appendChild(card);

        this.log(`${data.player}: ${data.survived ? '生还！' : '死亡...'}`);
    }

    // ========================================
    // Round End & Game Over
    // ========================================

    showRoundEnd(data) {
        this.showPhase('roundEnd');
        this.roundScores.innerHTML = '';

        data.scores.forEach(s => {
            const item = document.createElement('div');
            item.className = 'score-item';
            item.innerHTML = `
                <span class="name">${s.name}</span>
                <span class="score">${s.score}分</span>
            `;
            this.roundScores.appendChild(item);
        });

        // 更新顶部分数
        data.scores.forEach(s => {
            const chip = this.playersBar.querySelector(`[data-name="${s.name}"]`);
            if (chip) {
                chip.innerHTML = `<span class="name">${s.name}</span><span class="score">${s.score}分</span>`;
            }
        });
    }

    showGameOver(data) {
        this.showPhase('gameOver');
        this.finalRankings.innerHTML = '';

        const medals = ['🥇', '🥈', '🥉'];
        data.rankings.forEach((r, i) => {
            const item = document.createElement('div');
            item.className = 'score-item';
            item.innerHTML = `
                <span class="name">${medals[i] || ''} ${r.name}${r.is_bot ? ' (AI)' : ''}</span>
                <span class="score">${r.score}分</span>
            `;
            this.finalRankings.appendChild(item);
        });

        // 显示平分决胜理由
        if (data.tiebreaker_reason) {
            const reason = document.createElement('div');
            reason.className = 'tiebreaker-reason';
            reason.innerHTML = `<span>⚖️ 平分决胜理由：</span>${data.tiebreaker_reason}`;
            this.finalRankings.appendChild(reason);
        }
    }

    playAgain() {
        if (this.ws) {
            this.intentionalClose = true;
            this.ws.close();
        }
        this.showScreen('home');
    }
}

// Initialize
const game = new CrisisSurvivalGame();
