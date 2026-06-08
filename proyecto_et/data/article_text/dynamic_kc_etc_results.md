# Resultados de Kc dinámico y ETc espacial

Se construyó un Kc dinámico exploratorio a partir de índices espectrales Sentinel-2, usando SAVI como índice principal y NDVI como comparación metodológica. El Kc se escaló dentro del rango observado de cada índice en las fechas analysis-ready y se acotó entre 0.7 y 1.05. Por tanto, este Kc debe interpretarse como un coeficiente relativo de vigor/cobertura para el sitio y periodo analizado, no como un Kc universal calibrado.

La serie incluyó 8 fechas entre 2025-08-20 y 2025-12-28. El Kc dinámico basado en SAVI tuvo un valor medio de 0.862, con un rango temporal entre 0.783 y 0.935. Al multiplicar la ET base de estación por el Kc dinámico, la ETc SAVI media fue de 2.1 mm/día, con valores entre 1.409 y 2.702 mm/día.

En promedio, la ETc basada en SAVI representó el 86.19% de la ET base de estación, mientras que la ETc basada en NDVI representó el 87.84% de la ET base. La correlación entre ET base y ETc SAVI fue de r = 0.994; sin embargo, esta relación es esperable por construcción matemática, ya que ETc se calculó como ET base multiplicada por Kc dinámico.

El aporte principal de esta rama no es validar una ET satelital independiente, sino espacializar la ET de estación en función del estado espectral de la cobertura vegetal. En ese sentido, el producto Kc/ETc dinámico permite pasar de una señal puntual de estación a una superficie espacialmente variable dentro del ROI, conservando una interpretación exploratoria.
