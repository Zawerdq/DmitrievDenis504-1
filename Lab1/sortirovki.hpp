#ifndef SORTIROVKI_HPP
#define SORTIROVKI_HPP

void swap(int& a, int& b);
void bubble_sort(int arr[], int n);
void insertion_sort(int arr[], int n);
void selection_sort(int arr[], int n);
void quick_sort(int arr[], int Left, int Right);
void merge_sort(int arr[], int Left, int Right);
void merge(int arr[], int Left, int mid, int Right);
void heapify(int arr[], int n, int i);
void heap_sort(int arr[], int n);
#endif