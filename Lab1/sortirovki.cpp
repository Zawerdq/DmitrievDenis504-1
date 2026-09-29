#include "sortirovki.hpp"
void swap(int&a , int&b){
    if (&a == &b) return;
    a^=b;
    b^=a;
    a^=b;
}
void bubble_sort(int arr[],int n){
    for(int i=0;i<n-1;i++){
        bool changed = false;
        for(int j=0;j<n-1-i;j++){
            if(arr[j]>arr[j+1]){
                swap(arr[j],arr[j+1]);
                changed = true;
            }
        }
        if (!changed) break;
    }
}
void insertion_sort(int arr[], int n){
    for(int i=1;i<n;i++){
        for(int j=i;j>0;j--){
            if(arr[j]<arr[j-1]){
                swap(arr[j],arr[j-1]);
            }
            else{
                break;
            }
        }
    }
}
void selection_sort(int arr[], int n){
        for(int i=0;i<n-1;i++){
        int min_index=i;
        for(int j=i+1;j<n;j++){
            if (arr[j]<arr[min_index]){
                min_index=j;
            }
        }
        swap(arr[i],arr[min_index]);
    }
}
void quick_sort(int arr[], int Left , int Right){
    if (Left >= Right) return;
    int pivot=arr[(Left+Right)/2];
    int i=Left;
    int j=Right;
    while(i<=j){
        while(arr[i]<pivot) i++;
        while(arr[j]>pivot) j--;
        if(i<=j){
            swap(arr[i],arr[j]);
            i++;
            j--;
        }
    }
    quick_sort(arr,Left,j);
    quick_sort(arr,i,Right);
}
void merge(int arr[], int Left, int mid, int Right) {
    int n1 = mid - Left + 1;
    int n2 = Right - mid;
    int* L = new int[n1];
    int* R = new int[n2];
    for (int i = 0; i < n1; i++) {
        L[i] = arr[Left + i];
    }
    for (int j = 0; j < n2; j++) {
        R[j] = arr[mid + 1 + j];
    }
    int i = 0;
    int j = 0;
    int k = Left;
    while (i < n1 && j < n2) {
        if (L[i] <= R[j]) {
            arr[k] = L[i];
            i++;
        } else {
            arr[k] = R[j];
            j++;
        }

        k++;
    }
    while (i < n1) {
        arr[k] = L[i];
        i++;
        k++;
    }
    while (j < n2) {
        arr[k] = R[j];
        j++;
        k++;
    }
    delete[] L;
    delete[] R;
}
void merge_sort(int arr[], int Left, int Right){
    if(Left>=Right) return;
    int mid=(Left+Right)/2;
    merge_sort(arr,Left,mid);
    merge_sort(arr,mid+1,Right);
    merge(arr,Left,mid,Right);
}
void heapify(int arr[], int n,int i){
    int Largest=i;
    int Left=2*i+1;
    int Right=2*i+2;
    if(Left<n && arr[Left]>arr[Largest]){
        Largest=Left;
    }
    if(Right<n && arr[Right]>arr[Largest]){
        Largest=Right;
    }
    if(Largest!=i){
        swap(arr[i],arr[Largest]);
        heapify(arr,n,Largest);
    }
}
void heap_sort(int arr[], int n){
    for (int i=n/2-1;i>=0;i--){
        heapify(arr,n,i);
    }
    for(int i=n-1;i>0;i--){
        swap(arr[0],arr[i]);
        heapify(arr,i,0);
    }
}