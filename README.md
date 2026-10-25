# Onkyo Dimmer

Select-сущность для управления яркостью дисплея ресиверов Onkyo/Pioneer
(проверено на Pioneer VSX-LX505). Работает поверх встроенной интеграции
Onkyo и использует её соединение, поэтому второй слот eISCP не занимает.

## Установка через HACS
1. HACS - меню (три точки) - Custom repositories.
2. Добавьте URL репозитория, категория: Integration.
3. Установите Onkyo Dimmer, перезапустите Home Assistant.

## Настройка
В configuration.yaml:

    onkyo_dimmer:

Требуется настроенная встроенная интеграция Onkyo.
Режимы: bright, dim, dark, off (коды DIM00-DIM03).