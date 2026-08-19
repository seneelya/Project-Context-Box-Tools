// Edge.namespace.cpp — фикстура для «.»-уровня (transparent frame: namespace / extern "C").
// namespace структурно объемлет, но НЕ считается глубиной: помечается «.», а его содержимое
// остаётся на файловом level 1, чтобы не путалось.
//
// Проверять:  get_codeblock.py --file <this> --outline
// Ожидаемо:
//   //. [1-27]  namespace app        <- «.» = frame, не уровень (ведущий коммент приклеен -> с 1)
//   //1 [19-21] int helper(int x)     <- дети namespace остаются level 1
//   //1 [23-25] struct Config
//   //. [29-33] extern "C"            <- второй transparent-контейнер
//   //1 [30-32] int c_api(void)
//   //1 [35-37] int main()            <- ВНЕ namespace, но тот же level 1, что helper внутри:
//                                        namespace не углубляет, «.» = не глубина
//
// Заметка: «.» сейчас есть только в --outline; в --query (ладдер) namespace-ступени нет.

namespace app {

int helper(int x) {
	return x + 1;
}

struct Config {
	int n;
};

}  // namespace app

extern "C" {
int c_api(void) {
	return 0;
}
}

int main() {
	return app::helper(0);
}

// --- простые константы-переменные (однострочные, top-level) ---
const int MAX_RETRIES = 3;
constexpr double PI = 3.14159;
static const char* APP_NAME = "edge";

// --- компиляторные макро-константы (#define — текстовая замена, не переменные) ---
#define BUFFER_SIZE 4096
#define VERSION "1.0.0"
#define SQUARE(x) ((x) * (x))
