# Imagens Completas dos Elementos FDS

Este diretório contém TODAS as imagens necessárias para cada combinação de elemento, ângulo e mirror.

## Dimensões das Imagens
- Tamanho: 30x30 pixels (ESPAÇO COMPLETO!)
- Formato: PNG com transparência
- Grid do canvas: 30x30 pixels (sem margens)

## Recomendações para Pixel Art Fidedigna

### Espessura das Linhas (dentro de 30x30 pixels):
- **Trilhos principais**: 3-4 pixels de largura
- **Linhas de desvio (switches)**: 2-3 pixels de largura  
- **Sensores**: 3-4 pixels de largura
- **FMAs**: 3-4 pixels de largura

### Margens Recomendadas:
- **Margem mínima**: 2 pixels das bordas
- **Área útil**: 26x26 pixels para desenho
- **Centro**: pixel 15,15 (base 0)

### Cores Recomendadas:
- **Trilhos**: Preto (#000000) ou cinza escuro
- **Switches**: Trilho preto + desvio azul (#0000FF)
- **Sensores**: Vermelho (#FF0000) + símbolo
- **FMAs**: Verde (#00FF00) + caixa identificadora

## Lista Completa de Arquivos Necessários

### Trilhos (Rails) - 12 imagens
Ângulos simples (sem mirror): 0°, 180°
Ângulos estruturais (com mirror): 45°, 90°, 225°, 270°, 315°

```
rail_0_0.png    (horizontal simples)
rail_45_0.png   rail_45_1.png    (estruturas compostas)
rail_90_0.png   rail_90_1.png    (estruturas mistas)
rail_180_0.png  (vertical simples)
rail_225_0.png  rail_225_1.png   (estruturas diagonais/verticais)
rail_270_0.png  rail_270_1.png   (diagonais simples)
rail_315_0.png  rail_315_1.png   (estruturas verticais/diagonais)
```

### Chaves (Switches) - 10 imagens
Ângulos: 0°, 45°, 90°, 180°, 225°
Mirror: 0, 1 (para cada ângulo)

```
switch_0_0.png    switch_0_1.png
switch_45_0.png   switch_45_1.png
switch_90_0.png   switch_90_1.png
switch_180_0.png  switch_180_1.png
switch_225_0.png  switch_225_1.png
```

### Sensores - 8 imagens
Ângulos: 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°
(Sem mirror)

```
sensor_0.png    sensor_45.png   sensor_90.png   sensor_135.png
sensor_180.png  sensor_225.png  sensor_270.png  sensor_315.png
```

### FMAs - 4 imagens
Ângulos: 0°, 90°, 180°, 270°
(Sem mirror)

```
fma_0.png  fma_90.png  fma_180.png  fma_270.png
```

## Total: 34 imagens

## Descrição Visual por Ângulo

### Rails
- **0°**: Horizontal simples (sem mirror)
- **45°**: Estruturas compostas diagonais + horizontais
  - Mirror 0: "\_" (diagonal descendo + horizontal)
  - Mirror 1: "_/" (horizontal + diagonal subindo)
- **90°**: Estruturas horizontais + diagonais
  - Mirror 0: "--\" (horizontal + diagonal descendo)
  - Mirror 1: "/--" (diagonal subindo + horizontal)
- **180°**: Vertical simples (sem mirror)
- **225°**: Estruturas diagonais + verticais
  - Mirror 0: "|" + "/" (vertical + diagonal subindo)
  - Mirror 1: "\" + "|" (diagonal descendo + vertical)
- **270°**: Estruturas diagonais simples
  - Mirror 0: "/" (diagonal subindo)
  - Mirror 1: "\" (diagonal descendo)
- **315°**: Estruturas verticais + diagonais
  - Mirror 0: "|" + "\" (vertical + diagonal descendo)
  - Mirror 1: "/" + "|" (diagonal subindo + vertical)

### Switches
Similar aos rails, mas com linha diagonal adicional (azul) representando o desvio.

### Sensores
Linha vermelha com símbolo circular vermelho indicando a posição do sensor.

### FMAs
Linha verde com caixa contendo "F" para identificação.

## Como Substituir por Imagens Profissionais

1. Mantenha as dimensões exatas: **30x30 pixels**
2. Use transparência para fundo
3. Siga exatamente a nomenclatura dos arquivos
4. **Espessura recomendada**: 3-4 pixels para linhas principais
5. **Área de desenho**: 26x26 pixels (2px de margem)
6. Teste cada imagem no designer para verificar a aparência
7. Mantenha consistência visual entre elementos relacionados

### Dicas para Pixel Art Fidedigna:
- Use ferramentas como Aseprite, Photoshop (modo pixel art), ou GIMP
- Ative o grid/grade para visualizar pixels individuais
- Use cores sólidas sem anti-aliasing
- Linhas de 3-4 pixels ficam mais legíveis em 30x30
- Teste diferentes espessuras: 2px (fino), 3px (médio), 4px (grosso)

