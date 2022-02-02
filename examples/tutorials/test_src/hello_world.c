#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/time.h>

int main(int argc, char ** argv) {

    struct timeval tv;
    double lucky;

    gettimeofday(&tv, NULL);
    
    srandom(tv.tv_usec);
    lucky = (double)random()/RAND_MAX;

    // This prints a different message given an argument. 
    if (argc > 1) {
        printf("Hello %s!\n", argv[1]);
    } else {
        printf("Usage: ./hello <thing>\n");
        printf("I need to know what to say hello to.\n");
        return 1;
    }

    printf("Today's lucky number is: %0.4f\n", lucky);
    return 0;
}
