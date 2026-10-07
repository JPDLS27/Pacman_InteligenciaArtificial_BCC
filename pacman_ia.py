"""
Pac-Man com IA de busca adversarial
Disciplina de Inteligência Artificial

O Pac-Man é o jogador MAX e cada fantasma é um jogador MIN.
Algoritmos disponíveis (troque durante o jogo):
  1  - Minimax puro (sem poda)
  2  - Minimax com Poda Alfa-Beta
  3  - Expectimax (fantasmas tratados como aleatórios)
  M  - Controle manual (setas ou WASD)

Outros controles:
  + / -        aumenta / diminui a profundidade da busca (1 a 4)
  P ou ESPAÇO  pausa
  R            reinicia
  ESC          sai

Uso:
  pip install pygame
  python pacman_ia.py                 # abre o jogo
  python pacman_ia.py --benchmark     # compara os algoritmos sem interface gráfica
  python pacman_ia.py --benchmark 2   # idem, com profundidade 2 (padrão: 3)
"""

import math
import random
import sys
import time
from collections import deque

# =====================================================================
# 1. LABIRINTO
# =====================================================================
#  '#' parede   '.' comida   'o' cápsula (pílula de poder)
#  'P' Pac-Man  'G' fantasma ' ' vazio
#  '-' porta/casa dos fantasmas (só fantasmas passam)
#  Espaço vazio na borda = túnel: sair por um lado entra pelo outro
LAYOUT = [
    "###################",
    "#o.......#.......o#",
    "#.##.###.#.###.##.#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.###.#.###.####",
    "####.#.......#.####",
    "####.#.##-##.#.####",
    " ......#G-G#...... ",
    "####.#.#####.#.####",
    "####.#.......#.####",
    "####.#.#####.#.####",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#o.#.....P.....#.o#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#.................#",
    "###################",
]

DIRECOES = {"Norte": (0, -1), "Sul": (0, 1), "Leste": (1, 0), "Oeste": (-1, 0)}
OPOSTO = {"Norte": "Sul", "Sul": "Norte", "Leste": "Oeste", "Oeste": "Leste"}
TEMPO_SUSTO = 40  # quantos movimentos os fantasmas ficam assustados


LARGURA = len(LAYOUT[0])


def mover(pos, acao):
    if acao == "Parar":
        return pos
    dx, dy = DIRECOES[acao]
    return ((pos[0] + dx) % LARGURA, pos[1] + dy)  # % faz o túnel lateral


class Labirinto:
    def __init__(self, layout):
        self.altura = len(layout)
        self.largura = len(layout[0])
        self.paredes = set()
        self.comida = set()
        self.capsulas = set()
        self.inicio_fantasmas = []
        self.inicio_pac = None
        self.casa = set()  # porta e casa dos fantasmas: Pac-Man não entra

        for y, linha in enumerate(layout):
            assert len(linha) == self.largura, f"linha {y} com tamanho errado"
            for x, c in enumerate(linha):
                if c == "#":
                    self.paredes.add((x, y))
                elif c == ".":
                    self.comida.add((x, y))
                elif c == "o":
                    self.capsulas.add((x, y))
                elif c == "P":
                    self.inicio_pac = (x, y)
                elif c == "G":
                    self.inicio_fantasmas.append((x, y))
                    self.casa.add((x, y))
                elif c == "-":
                    self.casa.add((x, y))

        livres = [(x, y) for y in range(self.altura) for x in range(self.largura)
                  if (x, y) not in self.paredes]

        # Ações legais de cada célula (pré-calculadas para a busca ficar rápida)
        self.acoes = {}
        for p in livres:
            self.acoes[p] = [a for a in DIRECOES if mover(p, a) not in self.paredes]
        self.acoes_pac = {p: [a for a in self.acoes[p] if mover(p, a) not in self.casa]
                          for p in livres}

        # Distância real no labirinto entre todas as células (BFS a partir de cada uma)
        self.dist = {p: self._bfs(p) for p in livres}

    def _bfs(self, origem):
        dist = {origem: 0}
        fila = deque([origem])
        while fila:
            p = fila.popleft()
            for a in self.acoes[p]:
                q = mover(p, a)
                if q not in dist:
                    dist[q] = dist[p] + 1
                    fila.append(q)
        return dist


# =====================================================================
# 2. ESTADO DO JOGO (o "nó" da árvore de busca)
# =====================================================================
class Estado:
    lab = None  # labirinto compartilhado por todos os estados

    __slots__ = ("pac", "fantasmas", "assustado", "comida", "capsulas",
                 "pontos", "vitoria", "derrota")

    @classmethod
    def inicial(cls, lab):
        cls.lab = lab
        s = cls()
        s.pac = lab.inicio_pac
        s.fantasmas = list(lab.inicio_fantasmas)
        s.assustado = [0] * len(lab.inicio_fantasmas)
        s.comida = frozenset(lab.comida)
        s.capsulas = frozenset(lab.capsulas)
        s.pontos = 0
        s.vitoria = False
        s.derrota = False
        return s

    def copiar(self):
        s = Estado()
        s.pac = self.pac
        s.fantasmas = list(self.fantasmas)
        s.assustado = list(self.assustado)
        s.comida = self.comida
        s.capsulas = self.capsulas
        s.pontos = self.pontos
        s.vitoria = self.vitoria
        s.derrota = self.derrota
        return s

    def num_agentes(self):
        return 1 + len(self.fantasmas)  # agente 0 = Pac-Man, 1..n = fantasmas

    def terminal(self):
        return self.vitoria or self.derrota

    def acoes_legais(self, agente):
        if self.terminal():
            return []
        if agente == 0:
            return self.lab.acoes_pac[self.pac]
        return self.lab.acoes[self.fantasmas[agente - 1]]

    def sucessor(self, agente, acao):
        """Retorna o novo estado depois que 'agente' executa 'acao'."""
        s = self.copiar()
        if agente == 0:
            s.pac = mover(s.pac, acao)
            s.pontos -= 1  # custo por tempo: incentiva terminar rápido
            s.assustado = [max(0, t - 1) for t in s.assustado]
            if s.pac in s.comida:
                s.comida = s.comida - {s.pac}
                s.pontos += 10
            if s.pac in s.capsulas:
                s.capsulas = s.capsulas - {s.pac}
                s.pontos += 50
                s.assustado = [TEMPO_SUSTO] * len(s.fantasmas)
            for i in range(len(s.fantasmas)):
                s._colisao(i)
            if not s.derrota and not s.comida:
                s.vitoria = True
                s.pontos += 500
        else:
            i = agente - 1
            s.fantasmas[i] = mover(s.fantasmas[i], acao)
            s._colisao(i)
        return s

    def _colisao(self, i):
        if self.derrota or self.fantasmas[i] != self.pac:
            return
        if self.assustado[i] > 0:  # Pac-Man come o fantasma
            self.pontos += 200
            self.fantasmas[i] = self.lab.inicio_fantasmas[i]
            self.assustado[i] = 0
        else:  # fantasma pega o Pac-Man
            self.derrota = True
            self.pontos -= 500


# =====================================================================
# 3. FUNÇÃO DE AVALIAÇÃO (heurística usada quando a busca é cortada)
# =====================================================================
def avaliar(s):
    if s.terminal():
        return s.pontos

    d = s.lab.dist[s.pac]
    valor = s.pontos

    # Comida: quanto menos sobrar e quanto mais perto a próxima, melhor
    valor -= 15 * len(s.comida)
    if s.comida:
        valor -= 0.5 * min(d[f] for f in s.comida)

    # Fantasmas: fugir dos normais (penalidade cresce quanto mais perto)
    # e perseguir os assustados que dá tempo de alcançar
    perigo = [300, 300, 100, 40, 15, 5]
    for i, g in enumerate(s.fantasmas):
        dg = d[g]
        if s.assustado[i] > dg:
            valor += 50 - 2 * dg
        elif dg < len(perigo):
            valor -= perigo[dg]
    return valor


# =====================================================================
# 4. AGENTES DE BUSCA ADVERSARIAL
# =====================================================================
class AgenteBusca:
    nome = "Busca"

    def __init__(self, profundidade=2):
        self.profundidade = profundidade
        self.nos = 0  # nós expandidos na última decisão

    def proximo(self, agente, prof, s):
        """Quem joga depois de 'agente' e com qual profundidade restante.
        Uma 'rodada' completa (Pac-Man + todos os fantasmas) consome 1 de profundidade."""
        prox = (agente + 1) % s.num_agentes()
        return prox, (prof - 1 if prox == 0 else prof)

    def escolher(self, s):
        """Avalia cada ação do Pac-Man (raiz MAX) e escolhe a melhor.
        Empates são decididos aleatoriamente para evitar movimentos repetitivos."""
        self.nos = 0
        melhor, melhores = -math.inf, []
        alfa = -math.inf
        for acao in s.acoes_legais(0):
            filho = s.sucessor(0, acao)
            agente, prof = self.proximo(0, self.profundidade, s)
            v = self.valor(filho, prof, agente, alfa, math.inf)
            if v > melhor + 1e-9:
                melhor, melhores = v, [acao]
            elif abs(v - melhor) <= 1e-9:
                melhores.append(acao)
            alfa = max(alfa, melhor)
        return random.choice(melhores)

    def valor(self, s, prof, agente, alfa, beta):
        raise NotImplementedError


class AgenteMinimax(AgenteBusca):
    """Minimax clássico: explora a árvore inteira até a profundidade limite."""
    nome = "Minimax"

    def valor(self, s, prof, agente, alfa, beta):
        self.nos += 1
        if s.terminal() or prof == 0:
            return avaliar(s)
        prox, prox_prof = self.proximo(agente, prof, s)
        filhos = (self.valor(s.sucessor(agente, a), prox_prof, prox, alfa, beta)
                  for a in s.acoes_legais(agente))
        return max(filhos) if agente == 0 else min(filhos)


class AgenteAlfaBeta(AgenteBusca):
    """Minimax com Poda Alfa-Beta: mesmo resultado, menos nós expandidos.
    alfa = melhor valor já garantido para MAX no caminho até a raiz
    beta = melhor valor já garantido para MIN no caminho até a raiz"""
    nome = "Alfa-Beta"

    def valor(self, s, prof, agente, alfa, beta):
        self.nos += 1
        if s.terminal() or prof == 0:
            return avaliar(s)
        prox, prox_prof = self.proximo(agente, prof, s)

        if agente == 0:  # nó MAX (Pac-Man)
            v = -math.inf
            for a in s.acoes_legais(agente):
                v = max(v, self.valor(s.sucessor(agente, a), prox_prof, prox, alfa, beta))
                if v > beta:  # MIN nunca deixaria o jogo chegar aqui: poda
                    return v
                alfa = max(alfa, v)
            return v
        else:  # nó MIN (fantasma)
            v = math.inf
            for a in s.acoes_legais(agente):
                v = min(v, self.valor(s.sucessor(agente, a), prox_prof, prox, alfa, beta))
                if v < alfa:  # MAX já tem opção melhor em outro ramo: poda
                    return v
                beta = min(beta, v)
            return v


class AgenteExpectimax(AgenteBusca):
    """Expectimax: fantasmas viram nós de CHANCE (média dos filhos),
    supondo que eles escolhem as ações de forma uniforme e aleatória."""
    nome = "Expectimax"

    def valor(self, s, prof, agente, alfa, beta):
        self.nos += 1
        if s.terminal() or prof == 0:
            return avaliar(s)
        prox, prox_prof = self.proximo(agente, prof, s)
        valores = [self.valor(s.sucessor(agente, a), prox_prof, prox, alfa, beta)
                   for a in s.acoes_legais(agente)]
        if agente == 0:
            return max(valores)
        return sum(valores) / len(valores)


AGENTES = {"minimax": AgenteMinimax, "alfabeta": AgenteAlfaBeta, "expectimax": AgenteExpectimax}


# =====================================================================
# 5. COMPORTAMENTO REAL DOS FANTASMAS (não é ótimo, tem aleatoriedade)
# =====================================================================
class Fantasma:
    def __init__(self, indice, agressividade, rng):
        self.indice = indice  # 1, 2, ...
        self.agressividade = agressividade
        self.rng = rng

    def escolher(self, s, direcao_atual):
        pos = s.fantasmas[self.indice - 1]
        opcoes = list(s.lab.acoes[pos])
        # Como no jogo original, fantasmas evitam dar meia-volta
        if direcao_atual and len(opcoes) > 1 and OPOSTO[direcao_atual] in opcoes:
            opcoes.remove(OPOSTO[direcao_atual])

        if self.rng.random() < self.agressividade:
            d_pac = lambda a: s.lab.dist[mover(pos, a)][s.pac]
            if s.assustado[self.indice - 1] > 0:
                return max(opcoes, key=d_pac)  # foge
            return min(opcoes, key=d_pac)      # persegue
        return self.rng.choice(opcoes)


# =====================================================================
# 6. PARTIDA (lógica do jogo, sem interface gráfica)
# =====================================================================
class Partida:
    def __init__(self, lab, semente=None):
        self.lab = lab
        rng = random.Random(semente)
        self.estado = Estado.inicial(lab)
        self.anterior = self.estado
        self.dir_pac = "Oeste"
        self.dir_fant = [None] * len(lab.inicio_fantasmas)
        agressividades = [0.8, 0.6, 0.7, 0.5]
        self.fantasmas = [Fantasma(i + 1, agressividades[i % 4], rng)
                          for i in range(len(lab.inicio_fantasmas))]
        self.passos = 0

    @property
    def fim(self):
        return self.estado.terminal()

    def avancar(self, acao_pac):
        """Uma rodada: Pac-Man se move, depois cada fantasma."""
        self.anterior = self.estado
        if acao_pac != "Parar":
            self.dir_pac = acao_pac
        s = self.estado.sucessor(0, acao_pac)
        for i, f in enumerate(self.fantasmas):
            if s.terminal():
                break
            a = f.escolher(s, self.dir_fant[i])
            self.dir_fant[i] = a
            s = s.sucessor(i + 1, a)
        self.estado = s
        self.passos += 1 


# =====================================================================
# 7. BENCHMARK (compara os algoritmos, roda sem pygame)
# =====================================================================
def benchmark(profundidade=3, partidas=8, max_passos=800):
    lab = Labirinto(LAYOUT)
    print(f"\nBenchmark - profundidade {profundidade}, {partidas} partidas por algoritmo\n")
    print(f"{'Algoritmo':<12}{'Vitórias':>9}{'Pontos médios':>15}"
          f"{'Nós/decisão':>13}{'ms/decisão':>12}")
    print("-" * 61)
    for chave, Classe in AGENTES.items():
        vitorias, pontos, nos, tempo, decisoes = 0, 0, 0, 0.0, 0
        for semente in range(partidas):
            random.seed(semente)
            partida = Partida(lab, semente)
            agente = Classe(profundidade)
            while not partida.fim and partida.passos < max_passos:
                t0 = time.perf_counter()
                acao = agente.escolher(partida.estado)
                tempo += time.perf_counter() - t0
                nos += agente.nos
                decisoes += 1
                partida.avancar(acao)
            vitorias += partida.estado.vitoria
            pontos += partida.estado.pontos
        print(f"{Classe.nome:<12}{vitorias:>6}/{partidas:<2}{pontos / partidas:>15.1f}"
              f"{nos / decisoes:>13.0f}{1000 * tempo / decisoes:>12.1f}")
    print()


# =====================================================================
# 8. INTERFACE GRÁFICA (pygame)
# =====================================================================
CEL = 32
HUD = 96
PASSO_MS = 150  # tempo entre rodadas

PRETO = (0, 0, 0)
PAREDE = (18, 18, 80)
BORDA = (60, 90, 255)
COMIDA = (255, 205, 170)
AMARELO = (255, 230, 0)
BRANCO = (255, 255, 255)
AZUL_SUSTO = (40, 60, 230)
OLHO = (30, 40, 160)
CINZA = (170, 170, 170)
CORES_FANTASMAS = [(240, 40, 40), (255, 150, 210), (0, 230, 230), (255, 170, 60)]


class Jogo:
    def __init__(self):
        import pygame
        self.pg = pygame
        pygame.init()
        self.lab = Labirinto(LAYOUT)
        self.larg = self.lab.largura * CEL
        self.alt = self.lab.altura * CEL
        self.tela = pygame.display.set_mode((self.larg, self.alt + HUD))
        pygame.display.set_caption("Pac-Man - Busca Adversarial")
        self.fonte = pygame.font.SysFont("consolas,dejavusansmono,monospace", 15)
        self.fonte_grande = pygame.font.SysFont("arial,dejavusans", 40, bold=True)
        self.relogio = pygame.time.Clock()
        self.modo = "alfabeta"
        self.profundidade = 3
        self.reiniciar()

    def reiniciar(self):
        self.partida = Partida(self.lab)
        self.desejada = None
        self.pausado = False
        self.nos = 0
        self.ms_decisao = 0.0
        self.ultimo_passo = self.pg.time.get_ticks()

    # ---------- lógica ----------
    def passo(self):
        s = self.partida.estado
        if self.modo == "manual":
            legais = s.acoes_legais(0)
            if self.desejada in legais:
                acao = self.desejada
            elif self.partida.dir_pac in legais:
                acao = self.partida.dir_pac
            else:
                acao = "Parar"
            self.nos, self.ms_decisao = 0, 0.0
        else:
            agente = AGENTES[self.modo](self.profundidade)
            t0 = time.perf_counter()
            acao = agente.escolher(s)
            self.ms_decisao = 1000 * (time.perf_counter() - t0)
            self.nos = agente.nos
        self.partida.avancar(acao)

    def eventos(self):
        pg = self.pg
        teclas_dir = {pg.K_UP: "Norte", pg.K_w: "Norte", pg.K_DOWN: "Sul", pg.K_s: "Sul",
                      pg.K_LEFT: "Oeste", pg.K_a: "Oeste", pg.K_RIGHT: "Leste", pg.K_d: "Leste"}
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                return False
            if ev.type != pg.KEYDOWN:
                continue
            k = ev.key
            if k == pg.K_ESCAPE:
                return False
            elif k in teclas_dir:
                self.desejada = teclas_dir[k]
                if self.modo != "manual":
                    self.modo = "manual"
            elif k == pg.K_1:
                self.modo = "minimax"
            elif k == pg.K_2:
                self.modo = "alfabeta"
            elif k == pg.K_3:
                self.modo = "expectimax"
            elif k == pg.K_m:
                self.modo = "manual"
            elif k in (pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS):
                self.profundidade = min(4, self.profundidade + 1)
            elif k in (pg.K_MINUS, pg.K_KP_MINUS):
                self.profundidade = max(1, self.profundidade - 1)
            elif k in (pg.K_p, pg.K_SPACE):
                self.pausado = not self.pausado
            elif k == pg.K_r:
                self.reiniciar()
        return True

    # ---------- desenho ----------
    def interpolar(self, a, b, t):
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) > 1:  # teletransporte (fantasma comido)
            a = b
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        return int(x * CEL + CEL / 2), int(y * CEL + CEL / 2)

    def desenhar_labirinto(self):
        pg, tela = self.pg, self.tela
        for (x, y) in self.lab.paredes:
            r = pg.Rect(x * CEL, y * CEL, CEL, CEL)
            pg.draw.rect(tela, PAREDE, r)
            # contorno azul nos lados que encostam em corredores
            if (x, y - 1) not in self.lab.paredes and y > 0:
                pg.draw.line(tela, BORDA, r.topleft, r.topright, 2)
            if (x, y + 1) not in self.lab.paredes and y < self.lab.altura - 1:
                pg.draw.line(tela, BORDA, r.bottomleft, r.bottomright, 2)
            if (x - 1, y) not in self.lab.paredes and x > 0:
                pg.draw.line(tela, BORDA, r.topleft, r.bottomleft, 2)
            if (x + 1, y) not in self.lab.paredes and x < self.lab.largura - 1:
                pg.draw.line(tela, BORDA, r.topright, r.bottomright, 2)

        porta = (255, 150, 210)
        for (x, y) in self.lab.casa:
            if (x - 1, y) in self.lab.paredes and (x + 1, y) in self.lab.paredes:
                pg.draw.line(tela, porta, (x * CEL, y * CEL + CEL // 2),
                             ((x + 1) * CEL, y * CEL + CEL // 2), 4)

        s = self.partida.estado
        for (x, y) in s.comida:
            pg.draw.circle(tela, COMIDA, (x * CEL + CEL // 2, y * CEL + CEL // 2), 3)
        pulso = 6 + 2 * math.sin(pg.time.get_ticks() / 150)
        for (x, y) in s.capsulas:
            pg.draw.circle(tela, COMIDA, (x * CEL + CEL // 2, y * CEL + CEL // 2), int(pulso))

    def desenhar_pacman(self, cx, cy):
        r = CEL * 0.42
        ang = {"Leste": 0, "Norte": 90, "Oeste": 180, "Sul": 270}[self.partida.dir_pac]
        if self.partida.estado.derrota:
            abertura = 0
        else:
            abertura = 5 + 40 * abs(math.sin(self.pg.time.get_ticks() / 90))
        pts = [(cx, cy)]
        for k in range(31):
            a = math.radians(ang + abertura + (360 - 2 * abertura) * k / 30)
            pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
        self.pg.draw.polygon(self.tela, AMARELO, pts)

    def desenhar_fantasma(self, cx, cy, i):
        pg, tela = self.pg, self.tela
        r = CEL * 0.42
        susto = self.partida.estado.assustado[i]
        cor = CORES_FANTASMAS[i % len(CORES_FANTASMAS)]
        if susto > 0:
            piscar = susto <= 8 and (pg.time.get_ticks() // 200) % 2
            cor = BRANCO if piscar else AZUL_SUSTO

        topo = cy - r * 0.2
        base = cy + r * 0.6
        pg.draw.circle(tela, cor, (cx, int(topo)), int(r))
        pg.draw.rect(tela, cor, pg.Rect(cx - r, topo, 2 * r, base - topo))
        saia = [(cx - r, base)]
        for k in range(7):
            saia.append((cx - r + k * (2 * r / 6), base + (r * 0.4 if k % 2 == 0 else r * 0.1)))
        saia.append((cx + r, base))
        pg.draw.polygon(tela, cor, saia)

        if susto > 0:  # rostinho assustado
            for dx in (-0.3, 0.3):
                pg.draw.circle(tela, COMIDA, (int(cx + dx * r), int(cy - 0.25 * r)), 2)
            boca = [(cx - r * 0.5 + k * r * 0.2, cy + r * (0.25 if k % 2 else 0.1)) for k in range(6)]
            pg.draw.lines(tela, COMIDA, False, boca, 1)
        else:  # olhos olhando para a direção do movimento
            d = self.partida.dir_fant[i]
            ox, oy = DIRECOES[d] if d else (0, 0)
            for dx in (-0.35, 0.35):
                ex, ey = cx + dx * r, cy - 0.25 * r
                pg.draw.circle(tela, BRANCO, (int(ex), int(ey)), int(r * 0.28))
                pg.draw.circle(tela, OLHO, (int(ex + ox * r * 0.13), int(ey + oy * r * 0.13)), int(r * 0.14))

    def desenhar_hud(self):
        pg, tela = self.pg, self.tela
        s = self.partida.estado
        y0 = self.alt + 6
        nome_modo = "Manual" if self.modo == "manual" else AGENTES[self.modo].nome
        linhas = [
            (f"Pontos: {s.pontos:<6}  Comida restante: {len(s.comida):<4}  Rodada: {self.partida.passos}", BRANCO),
            (f"Modo: {nome_modo:<11} Profundidade: {self.profundidade}", AMARELO),
            (f"Nós expandidos: {self.nos:<7} Tempo da decisão: {self.ms_decisao:.1f} ms", AMARELO),
            ("1/2/3 Algoritmo  M Manual  +/- Prof.  P Pausa  R Reinicia", CINZA),
        ]
        for i, (txt, cor) in enumerate(linhas):
            tela.blit(self.fonte.render(txt, True, cor), (10, y0 + i * 22))

    def desenhar_aviso(self, texto, cor):
        pg = self.pg
        veu = pg.Surface((self.larg, self.alt), pg.SRCALPHA)
        veu.fill((0, 0, 0, 150))
        self.tela.blit(veu, (0, 0))
        t = self.fonte_grande.render(texto, True, cor)
        self.tela.blit(t, t.get_rect(center=(self.larg // 2, self.alt // 2 - 15)))
        sub = self.fonte.render("Pressione R para jogar de novo", True, BRANCO)
        self.tela.blit(sub, sub.get_rect(center=(self.larg // 2, self.alt // 2 + 25)))

    def desenhar(self):
        self.tela.fill(PRETO)
        self.desenhar_labirinto()
        agora = self.pg.time.get_ticks()
        t = 1.0 if (self.pausado or self.partida.fim) else min(1.0, (agora - self.ultimo_passo) / PASSO_MS)
        ant, atual = self.partida.anterior, self.partida.estado
        for i in range(len(atual.fantasmas)):
            self.desenhar_fantasma(*self.interpolar(ant.fantasmas[i], atual.fantasmas[i], t), i)
        self.desenhar_pacman(*self.interpolar(ant.pac, atual.pac, t))
        self.desenhar_hud()
        if atual.vitoria:
            self.desenhar_aviso("VITÓRIA!", AMARELO)
        elif atual.derrota:
            self.desenhar_aviso("FIM DE JOGO", (255, 70, 70))
        elif self.pausado:
            self.desenhar_aviso("PAUSADO", BRANCO)
        self.pg.display.flip()

    def rodar(self):
        rodando = True
        while rodando:
            rodando = self.eventos()
            agora = self.pg.time.get_ticks()
            if not self.pausado and not self.partida.fim and agora - self.ultimo_passo >= PASSO_MS:
                self.passo()
                self.ultimo_passo = self.pg.time.get_ticks()
            self.desenhar()
            self.relogio.tick(60)
        self.pg.quit()


if __name__ == "__main__":
    if "--benchmark" in sys.argv:
        args = [a for a in sys.argv[1:] if a.isdigit()]
        benchmark(int(args[0]) if args else 3)
    else:
        Jogo().rodar()
