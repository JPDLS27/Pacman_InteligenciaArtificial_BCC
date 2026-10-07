# Pac-Man com IA de Busca Adversarial

Trabalho da disciplina de Inteligência Artificial: um Pac-Man em Python (pygame) em que o Pac-Man é controlado por algoritmos de busca adversarial.

- **Pac-Man = MAX**, **cada fantasma = uma camada MIN** na árvore de jogo
- Algoritmos: **Minimax**, **Minimax com Poda Alfa-Beta** e **Expectimax**
- Função de avaliação heurística (pontuação, comida restante, distância à comida, perigo dos fantasmas, perseguição de fantasmas assustados)
- HUD mostra nós expandidos e tempo de cada decisão

## Como rodar

```bash
pip install -r requirements.txt
python pacman_ia.py               # abre o jogo
python pacman_ia.py --benchmark   # compara os algoritmos sem interface (profundidade 3)
python pacman_ia.py --benchmark 2 # idem, profundidade 2
```

## Controles

| Tecla | Ação |
|---|---|
| `1` / `2` / `3` | Minimax / Alfa-Beta / Expectimax |
| `M` ou setas/WASD | Controle manual |
| `+` / `-` | Aumenta / diminui a profundidade (1 a 4) |
| `P` ou `Espaço` | Pausa |
| `R` | Reinicia |
| `Esc` | Sai |

## Resultados (profundidade 3, 8 partidas)

| Algoritmo | Vitórias | Pontos médios | Nós/decisão | ms/decisão |
|---|---|---|---|---|
| Minimax | 4/8 | 1810 | 3489 | 19,8 |
| Alfa-Beta | 4/8 | 1810 | 1362 | 6,9 |
| Expectimax | 0/8 | 357 | 3464 | 28,1 |

- O Alfa-Beta chega **ao mesmo resultado** do Minimax expandindo ~60% menos nós.
- O Expectimax supõe fantasmas aleatórios, mas eles perseguem o Pac-Man de propósito: o modelo errado do oponente piora o desempenho.

## Estrutura do código

1. `Labirinto` – layout, ações legais e distâncias reais (BFS) entre células
2. `Estado` – nó da árvore de busca; gera sucessores para cada agente
3. `avaliar` – função de avaliação usada quando a busca é cortada
4. `AgenteMinimax`, `AgenteAlfaBeta`, `AgenteExpectimax` – os algoritmos
5. `Fantasma` – comportamento real dos fantasmas (perseguição com aleatoriedade)
6. `Partida` – lógica do jogo sem interface
7. `benchmark` – comparação dos algoritmos
8. `Jogo` – interface gráfica em pygame
