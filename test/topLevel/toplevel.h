// toplevel.h — фиктивные данные для теста .0 (C++ header, макросы + рамки)

#ifndef TOPLEVEL_H
#define TOPLEVEL_H

#define MAX_BOXES 12
#define VERSION "1.0"
#define SQUARE(x) ((x) * (x))

namespace fruit {

constexpr int RIPE = 2;

struct Apple {
    int weight;
};

enum class Color { Red, Green, Blue };

}  // namespace fruit

extern "C" {
int ship(int n);
}

#endif  // TOPLEVEL_H
